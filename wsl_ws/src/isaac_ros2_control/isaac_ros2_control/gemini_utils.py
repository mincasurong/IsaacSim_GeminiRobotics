"""Utilities for image encoding, Gemini response parsing, and 2D-to-3D projection."""
import numpy as np
import json
import re


def encode_image_to_bytes(cv_image, fmt='png'):
    """Encode an OpenCV BGR image to PNG or JPEG bytes.

    Args:
        cv_image: OpenCV BGR image (numpy array).
        fmt: Output format, 'png' or 'jpeg'.

    Returns:
        bytes: Encoded image bytes.
    """
    import cv2
    if fmt == 'jpeg':
        _, buf = cv2.imencode('.jpg', cv_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    else:
        _, buf = cv2.imencode('.png', cv_image)
    return buf.tobytes()


def parse_gemini_response(response_text):
    """Parse Gemini's JSON response, stripping code fences if present.

    Args:
        response_text: Raw text from Gemini API response.

    Returns:
        Parsed JSON (list or dict).

    Raises:
        json.JSONDecodeError: If the response is not valid JSON.
    """
    text = response_text.strip()
    # Strip markdown code fences
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return json.loads(text)


def normalized_2d_to_pixel(y_norm, x_norm, img_height, img_width):
    """Convert Gemini's normalized [y, x] (0-1000) to pixel coordinates.

    Args:
        y_norm: Normalized y coordinate (0-1000).
        x_norm: Normalized x coordinate (0-1000).
        img_height: Image height in pixels.
        img_width: Image width in pixels.

    Returns:
        tuple: (py, px) pixel coordinates, clipped to image bounds.
    """
    px = int(x_norm / 1000.0 * img_width)
    py = int(y_norm / 1000.0 * img_height)
    px = np.clip(px, 0, img_width - 1)
    py = np.clip(py, 0, img_height - 1)
    return int(py), int(px)


def pixel_to_3d_world(px, py, depth_image, camera_intrinsics, camera_extrinsics):
    """Back-project a pixel coordinate to 3D world coordinates using depth.

    Args:
        px: Pixel x coordinate.
        py: Pixel y coordinate.
        depth_image: HxW depth image in meters.
        camera_intrinsics: 3x3 camera intrinsic matrix.
        camera_extrinsics: 4x4 camera-to-world transform.

    Returns:
        numpy.ndarray: [x, y, z] world coordinates, or None if depth is invalid.
    """
    z = depth_image[py, px]
    if z <= 0 or z > 10.0:
        return None

    fx, fy = camera_intrinsics[0, 0], camera_intrinsics[1, 1]
    cx, cy = camera_intrinsics[0, 2], camera_intrinsics[1, 2]

    x_cam = (px - cx) * z / fx
    y_cam = (py - cy) * z / fy
    z_cam = z

    p_cam = np.array([x_cam, y_cam, z_cam, 1.0])
    p_world = camera_extrinsics @ p_cam
    return p_world[:3]


def gemini_points_to_3d(detections, depth_image, camera_intrinsics, camera_extrinsics):
    """Convert a list of Gemini detection dicts to 3D world coordinates.

    Args:
        detections: List of {"point": [y, x], "label": str} dicts.
        depth_image: HxW depth image in meters.
        camera_intrinsics: 3x3 camera intrinsic matrix.
        camera_extrinsics: 4x4 camera-to-world transform.

    Returns:
        List of {"label": str, "world_pos": [x, y, z]} dicts.
    """
    h, w = depth_image.shape[:2]
    results = []
    for det in detections:
        y_norm, x_norm = det['point']
        py, px = normalized_2d_to_pixel(y_norm, x_norm, h, w)
        world_pos = pixel_to_3d_world(px, py, depth_image, camera_intrinsics, camera_extrinsics)
        if world_pos is not None:
            results.append({
                'label': det['label'],
                'world_pos': world_pos.tolist(),
                'pixel': [py, px],
                'normalized': [y_norm, x_norm]
            })
    return results


def resolve_object_key(target_str: str, available_keys=None) -> str:
    """Resolve a freeform label, alias, or name to a canonical object prim name.

    Supports:
    - Kitchenware dishes/plates: 'Dish1'..'Dish3', 'white dish', 'blue plate', 'terracotta', etc.
    - Kitchenware cups/mugs: 'Cup1'..'Cup3', 'amber mug', 'sage', 'charcoal', etc.
    - Kitchenware long bar: 'LongBar1', 'long bar', 'tray', 'serving tray', etc.
    - Blocks / cubes: 'Block1'..'Block9', 'Red Cube', 'green', etc.
    - Punctuation stripping: e.g. 'Dish#1!' -> 'Dish1'.
    - Exact match & case-insensitive match against available_keys.
    - Safe None return on empty, None, whitespace, or unresolvable targets.

    Args:
        target_str: Freeform label or name string.
        available_keys: Optional list, set, tuple, or dict of available object names.

    Returns:
        Canonical object name (e.g. 'Dish1', 'Cup2', 'LongBar1', 'Block3'), or None.
    """
    if target_str is None:
        return None

    raw = str(target_str).strip()
    if not raw:
        return None

    # Handle available_keys normalization
    avail_map = {}  # lowercase_str -> exact_key_in_available
    if available_keys is not None:
        if isinstance(available_keys, dict):
            for k, v in available_keys.items():
                avail_map[str(k).lower()] = str(v)
                avail_map[str(v).lower()] = str(v)
        elif isinstance(available_keys, (list, tuple, set)):
            for item in available_keys:
                avail_map[str(item).lower()] = str(item)

    # 1. Exact match against available_keys
    if avail_map:
        if raw in avail_map.values():
            return raw
        if raw.lower() in avail_map:
            return avail_map[raw.lower()]

    # 2. Clean punctuation / special characters (retain alphanumeric and spaces/underscores)
    s_clean = re.sub(r'[^a-zA-Z0-9_\s]', '', raw).strip()
    if not s_clean:
        return None

    if avail_map and s_clean.lower() in avail_map:
        return avail_map[s_clean.lower()]

    l = s_clean.lower()
    tokens = set(re.findall(r'[a-zA-Z0-9]+', l))

    # Reject obvious non-existent or negative indicators
    if 'nonexistent' in tokens or 'invalid' in tokens or 'unknown' in tokens:
        return None

    # 3. Numeric string disambiguation (e.g. target is '1' or '2')
    if l.isdigit():
        d = l
        if avail_map:
            for k_lower, canonical in avail_map.items():
                if k_lower.endswith(d) or re.search(rf'\b{d}\b', k_lower):
                    return canonical
        if 1 <= int(d) <= 9:
            candidate = f"Block{d}"
            if not avail_map or candidate.lower() in avail_map:
                return candidate
        return None

    resolved = None

    # 4. Semantic / descriptive label classification

    # Exact block colors and numbered blocks
    if 'red' in tokens or 'block1' in tokens or l == 'red cube':
        if 'dish' in l or 'plate' in l:
            resolved = 'Dish3'
        else:
            resolved = 'Block1'
    elif 'green' in tokens or 'block2' in tokens:
        if 'cup' in l or 'mug' in l:
            resolved = 'Cup2'
        else:
            resolved = 'Block2'
    elif ('blue' in tokens and ('block' in l or 'cube' in l or 'cylinder' in l or '3' in l)) or 'block3' in tokens:
        resolved = 'Block3'
    elif ('yellow' in tokens and ('block' in l or 'cube' in l or 'cylinder' in l or '4' in l)) or 'block4' in tokens:
        resolved = 'Block4'
    elif 'magenta' in tokens or 'block5' in tokens:
        resolved = 'Block5'
    elif 'cyan' in tokens or 'block6' in tokens:
        resolved = 'Block6'
    elif 'orange' in tokens or 'block7' in tokens:
        resolved = 'Block7'
    elif 'purple' in tokens or 'block8' in tokens:
        resolved = 'Block8'
    elif 'lime' in tokens or 'block9' in tokens:
        resolved = 'Block9'
    elif 'block' in tokens or l.startswith('block'):
        digits = ''.join([c for c in l if c.isdigit()])
        if digits and 1 <= int(digits) <= 9:
            resolved = f"Block{digits}"
        else:
            resolved = 'Block1'

    # Kitchen dishes / plates
    if not resolved:
        if 'dish1' in tokens or 'plate1' in tokens or 'white dish' in l or 'white plate' in l or 'porcelain' in l or 'shallow plate' in l:
            resolved = 'Dish1'
        elif 'dish2' in tokens or 'plate2' in tokens or 'blue dish' in l or 'blue plate' in l or 'cobalt' in l or 'nordic' in l:
            resolved = 'Dish2'
        elif 'dish3' in tokens or 'plate3' in tokens or 'terracotta' in l or 'clay' in l or 'red dish' in l or 'red plate' in l:
            resolved = 'Dish3'
        elif 'dish' in tokens or 'plate' in tokens or 'saucer' in tokens or 'dishes' in tokens or 'plates' in tokens:
            digits = ''.join([c for c in l if c.isdigit()])
            if digits and 1 <= int(digits) <= 3:
                resolved = f"Dish{digits}"
            else:
                resolved = 'Dish1'

    # Kitchen cups / mugs
    if not resolved:
        if 'cup1' in tokens or 'mug1' in tokens or 'amber' in l or 'mustard' in l or 'yellow cup' in l or 'yellow mug' in l or 'ceramic cup' in l:
            resolved = 'Cup1'
        elif 'cup2' in tokens or 'mug2' in tokens or 'sage' in l or 'mint' in l or 'green cup' in l or 'green mug' in l:
            resolved = 'Cup2'
        elif 'cup3' in tokens or 'mug3' in tokens or 'charcoal' in l or 'espresso' in l or 'black cup' in l or 'black mug' in l:
            resolved = 'Cup3'
        elif 'cup' in tokens or 'mug' in tokens or 'coffee cup' in l or 'cups' in tokens or 'mugs' in tokens:
            digits = ''.join([c for c in l if c.isdigit()])
            if digits and 1 <= int(digits) <= 3:
                resolved = f"Cup{digits}"
            else:
                resolved = 'Cup1'

    # Long bar / serving tray (collaborative dual-arm object)
    if not resolved:
        if 'longbar' in l or 'long_bar' in l or 'long bar' in l or 'bar' in tokens or 'tray' in tokens or 'serving tray' in l or 'serving_tray' in l:
            digits = ''.join([c for c in l if c.isdigit()])
            if digits and 1 <= int(digits) <= 3:
                resolved = f"LongBar{digits}"
            else:
                resolved = 'LongBar1'

    # 5. Canonical pattern check: Dish1..3, Cup1..3, LongBar1..3, Block1..9
    if not resolved:
        for prefix in ['Dish', 'Cup', 'LongBar', 'Block']:
            if l.startswith(prefix.lower()):
                suffix = l[len(prefix):].strip(' _-')
                if suffix.isdigit():
                    resolved = f"{prefix}{suffix}"
                    break

    # 6. Validate against avail_map if provided
    if resolved:
        if avail_map:
            if resolved.lower() in avail_map:
                return avail_map[resolved.lower()]
            return None
        return resolved

    # 7. Fallback fuzzy check on avail_map if provided
    if avail_map:
        for k_lower, canonical in avail_map.items():
            if k_lower in l or l in k_lower:
                return canonical

    return None


def resolve_block_key(label: str, available_keys=None) -> str:
    """Backward-compatible alias for resolve_object_key."""
    return resolve_object_key(label, available_keys=available_keys)


def get_object_type(label: str) -> str:
    """Classify target object into affordance taxonomy: 'dish', 'cup', 'long_bar', or 'block'."""
    if not label:
        return 'block'
    resolved = resolve_object_key(label) or str(label)
    l = resolved.lower()
    if 'dish' in l or 'plate' in l or 'saucer' in l:
        return 'dish'
    elif 'cup' in l or 'mug' in l:
        return 'cup'
    elif 'bar' in l or 'tray' in l:
        return 'long_bar'
    return 'block'


def is_dual_arm_object(label: str) -> bool:
    """Check if the object requires dual-arm collaborative manipulation."""
    return get_object_type(label) == 'long_bar'


def is_kitchenware(label: str) -> bool:
    """Check if the object is kitchenware (dish, cup, or long bar)."""
    return get_object_type(label) in ('dish', 'cup', 'long_bar')

