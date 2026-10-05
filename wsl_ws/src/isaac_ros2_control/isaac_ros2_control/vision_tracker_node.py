"""Real-Time 3D Vision Tracker Node for Isaac Sim RGB-D Camera Stream.

SOLID Architecture (SOTA October 2026):
- Single Responsibility:
  * PinholeCameraProjector: Encapsulates camera intrinsics and 3D back-projection geometry.
  * SpatialObjectSegmenter: Encapsulates depth-masked contour segmentation and 3D shape classification.
  * VisionTrackerNode: Orchestrates ROS 2 subscriptions, frame timing, and publisher telemetry.
- Open/Closed:
  * Easily extendable for new object types or alternative detector backends (e.g. YOLO ONNX) without altering ROS logic.
"""

import json
import time
from typing import Dict, Any, Tuple, Optional
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import String

try:
    import cv2
except ImportError:
    cv2 = None


class PinholeCameraProjector:
    """Encapsulates Pinhole Camera Model and 2D-to-3D back-projection geometry."""

    def __init__(
        self,
        position_w: Tuple[float, float, float] = (0.0, 0.4, 2.0),
        fx: float = 600.0,
        fy: float = 600.0,
        cx: float = 320.0,
        cy: float = 240.0,
    ):
        self.cam_pos_w = np.array(position_w, dtype=float)
        # Camera Optical Frame to World Frame: +X_cam -> +X_w, +Y_cam -> -Y_w, +Z_cam -> -Z_w (downward)
        self.R_cam_to_world = np.array([
            [1.0,  0.0,  0.0],
            [0.0, -1.0,  0.0],
            [0.0,  0.0, -1.0]
        ], dtype=float)

        self.fx = fx
        self.fy = fy
        self.cx = cx
        self.cy = cy

    def update_intrinsics(self, k_matrix: list):
        """Update intrinsics from CameraInfo message K array."""
        if len(k_matrix) >= 9 and k_matrix[0] > 0:
            self.fx = float(k_matrix[0])
            self.fy = float(k_matrix[4])
            self.cx = float(k_matrix[2])
            self.cy = float(k_matrix[5])

    def pixel_to_world(self, u: float, v: float, depth_z: float) -> np.ndarray:
        """Convert image pixel (u, v) and depth Z to 3D world coordinate [X, Y, Z]."""
        x_cam = (u - self.cx) * depth_z / self.fx
        y_cam = (v - self.cy) * depth_z / self.fy
        p_cam = np.array([x_cam, y_cam, depth_z], dtype=float)
        return self.R_cam_to_world @ p_cam + self.cam_pos_w


class SpatialObjectSegmenter:
    """Segments foreground objects using depth masks and classifies 3D shapes."""

    def __init__(self, projector: PinholeCameraProjector):
        self.projector = projector

    def detect_objects(self, rgb_img: np.ndarray, depth_img: np.ndarray) -> Dict[str, Dict[str, Any]]:
        """Extract foreground objects and return structured 3D world centroid coordinates."""
        h, w = depth_img.shape
        tracked_objects: Dict[str, Dict[str, Any]] = {}

        if cv2 is not None and rgb_img is not None:
            # Depth mask: filter workbench & conveyor surface range
            valid_depth_mask = (depth_img > 0.8) & (depth_img < 1.9)

            gray = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            _, thresh = cv2.threshold(blurred, 40, 255, cv2.THRESH_BINARY_INV)

            combined = cv2.bitwise_and(thresh, thresh, mask=valid_depth_mask.astype(np.uint8) * 255)
            contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            item_idx = 0
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if 120 < area < 12000:
                    M = cv2.moments(cnt)
                    if M["m00"] > 0:
                        u = int(M["m10"] / M["m00"])
                        v = int(M["m01"] / M["m00"])

                        u_min, u_max = max(0, u - 2), min(w, u + 3)
                        v_min, v_max = max(0, v - 2), min(h, v + 3)
                        depth_region = depth_img[v_min:v_max, u_min:u_max]
                        valid_z = depth_region[(depth_region > 0.5) & (depth_region < 2.0)]

                        if len(valid_z) > 0:
                            z_val = float(np.median(valid_z))
                            p_w = self.projector.pixel_to_world(u, v, z_val)

                            rect = cv2.minAreaRect(cnt)
                            box_w, box_h = rect[1]
                            aspect = max(box_w, box_h) / max(1.0, min(box_w, box_h))

                            label = self._classify_label(p_w, aspect, item_idx)
                            if 'ConvItem' in label or 'WorkplaceObj' in label:
                                item_idx += 1

                            tracked_objects[label] = {
                                "world_xyz": [round(float(p_w[0]), 3), round(float(p_w[1]), 3), round(float(p_w[2]), 3)],
                                "pixel_uv": [u, v],
                                "depth_m": round(z_val, 3),
                                "area_px": int(area),
                            }

        # Center fallback if contours empty
        if not tracked_objects and depth_img is not None:
            z_center = float(depth_img[240, 320])
            if 0.5 < z_center < 1.9:
                p_w = self.projector.pixel_to_world(320, 240, z_center)
                tracked_objects["CenterTarget"] = {
                    "world_xyz": [round(float(p_w[0]), 3), round(float(p_w[1]), 3), round(float(p_w[2]), 3)],
                    "pixel_uv": [320, 240],
                    "depth_m": round(z_center, 3)
                }

        return tracked_objects

    @staticmethod
    def _classify_label(p_w: np.ndarray, aspect_ratio: float, item_idx: int) -> str:
        """Classify object label based on physical position and geometric aspect ratio."""
        if aspect_ratio > 3.0 and p_w[1] < 0.0:
            return "LongBar"
        if aspect_ratio > 2.0 and p_w[1] < -0.3:
            return "HeavyEnginePart"
        if p_w[1] > 0.35:
            return f"ConvItem{item_idx}"
        return f"WorkplaceObj{item_idx}"


class VisionTrackerNode(Node):
    """ROS 2 Node providing real-time 3D visual tracking from RGB-D feeds."""

    def __init__(self):
        super().__init__('vision_tracker_node')

        self.projector = PinholeCameraProjector()
        self.segmenter = SpatialObjectSegmenter(self.projector)

        self.latest_rgb: Optional[np.ndarray] = None
        self.latest_depth: Optional[np.ndarray] = None

        # Subscribers
        self.rgb_sub = self.create_subscription(
            Image, '/overhead_camera/rgb', self._rgb_cb, 10)
        self.depth_sub = self.create_subscription(
            Image, '/overhead_camera/depth', self._depth_cb, 10)
        self.info_sub = self.create_subscription(
            CameraInfo, '/overhead_camera/camera_info', self._info_cb, 10)

        # Publisher
        self.tracked_pub = self.create_publisher(
            String, '/gemini/vision_tracked_objects', 10)

        # 30 Hz Visual Tracking Timer
        self.timer = self.create_timer(0.033, self._process_tracking)

        self.get_logger().info("VisionTrackerNode initialized (SOLID Pinhole Camera Back-Projection Engine).")

    def _info_cb(self, msg: CameraInfo):
        self.projector.update_intrinsics(list(msg.k))

    def _rgb_cb(self, msg: Image):
        try:
            w, h = msg.width, msg.height
            if msg.encoding in ['rgba8', 'bgra8']:
                img = np.frombuffer(msg.data, dtype=np.uint8).reshape((h, w, 4))
                self.latest_rgb = img[:, :, :3]
            elif msg.encoding in ['rgb8', 'bgr8']:
                self.latest_rgb = np.frombuffer(msg.data, dtype=np.uint8).reshape((h, w, 3))
        except Exception:
            pass

    def _depth_cb(self, msg: Image):
        try:
            w, h = msg.width, msg.height
            if msg.encoding == '32FC1':
                self.latest_depth = np.frombuffer(msg.data, dtype=np.float32).reshape((h, w))
        except Exception:
            pass

    def _process_tracking(self):
        if self.latest_rgb is None or self.latest_depth is None:
            return

        tracked_objects = self.segmenter.detect_objects(self.latest_rgb, self.latest_depth)

        msg = String()
        msg.data = json.dumps({
            "timestamp": time.time(),
            "camera_pos": list(self.projector.cam_pos_w),
            "objects": tracked_objects
        })
        self.tracked_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = VisionTrackerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
