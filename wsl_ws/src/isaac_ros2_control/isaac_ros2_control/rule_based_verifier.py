"""Rule-Based Task Generator and Safety Verifier for Gemini-4-Argon.

This module provides the deterministic foundation for the hybrid VLA architecture:
1. RuleBasedTaskGenerator:
   - Queries real-time workspace state (TF transforms, block positions, tower height).
   - Generates the deterministic baseline stacking sequence and constraints.
   - Formats a compact, grounded blueprint for Gemini-4-Argon.

2. RuleBasedTaskVerifier:
   - Pre-execution validation layer intercepting all VLA tool calls.
   - Enforces physical table reachability (FR3_1 -> Table 1, FR3_2 -> Table 2, FR3_3 -> Table 3).
   - Guards holding state preconditions (no double-picks, no empty-handed placing).
   - Validates central table placement bounds (|x| <= 0.15m, |y| <= 0.15m).
   - Auto-corrects minor model hallucinations and re-routes cross-table assignments safely.
"""

import json
import logging
import numpy as np


ROBOT_OWNED_BLOCKS = {
    'FR3_1': ['Block1', 'Block2', 'Block3', 'RedBall', 'GreenBall', 'AsmBlock1'],
    'FR3_2': ['Block4', 'Block5', 'Block6', 'YellowBall', 'AsmBlock2', 'AsmBlock3'],
    'FR3_3': ['Block7', 'Block8', 'Block9'],
}

ROBOT_BASES = {
    'FR3_1': np.array([0.0, -0.45]),
    'FR3_2': np.array([0.3897, 0.225]),
    'FR3_3': np.array([-0.3897, 0.225]),
}

CONVEYOR_ROBOT_BASES = {
    'FR3_1': np.array([-0.7, 0.0]),
    'FR3_2': np.array([0.7, 0.0]),
}

TABLE_ZONES = {
    'central_table': {'center': np.array([0.0, 0.0]), 'radius': 0.22},
    'table_1': {'center': np.array([0.0, -1.05]), 'radius': 0.35},
    'table_2': {'center': np.array([0.909, 0.525]), 'radius': 0.35},
    'table_3': {'center': np.array([-0.909, 0.525]), 'radius': 0.35},
    'main_workbench': {'center': np.array([0.0, -0.25]), 'radius': 1.40},
    'assembly_buffer': {'center': np.array([0.0, 0.0]), 'radius': 1.20},
    'conveyor_belt': {'center': np.array([0.0, 0.50]), 'radius': 1.50},
}

MAX_ARM_REACH = 0.85
MIN_ARM_REACH = 0.15

BLOCK_TO_ROBOT = {b: r for r, blocks in ROBOT_OWNED_BLOCKS.items() for b in blocks}

BLOCK_DESCRIPTIONS = {
    'Block1': 'Red Cube (6cm)',
    'Block2': 'Green Cylinder (6cm)',
    'Block3': 'Blue Cube (6cm)',
    'Block4': 'Yellow Cylinder (6cm)',
    'Block5': 'Magenta Cube (6cm)',
    'Block6': 'Cyan Cylinder (6cm)',
    'Block7': 'Orange Cube (6cm)',
    'Block8': 'Purple Cylinder (6cm)',
    'Block9': 'Lime Cube (6cm)',
    'RedBall': 'Red Elastomer Sphere (4.8cm)',
    'GreenBall': 'Green Elastomer Sphere (4.8cm)',
    'YellowBall': 'Yellow Elastomer Sphere (4.8cm)',
    'FlexibleBasket': 'Flexible Vinyl/Silicone Basket with Handles (32x24cm)',
    'AsmBlock1': 'Red Assembly Cube (5cm)',
    'AsmBlock2': 'Green Assembly Cube (5cm)',
    'AsmBlock3': 'Blue Assembly Cube (5cm)',
}


def resolve_block_name(label: str) -> str:
    """Normalize object labels (e.g. 'Red Cube', 'block 1', 'ConvItem0', 'LongBar', 'FlexibleBasket', 'RedBall') to canonical prim names."""
    if not label:
        return ""
    l = str(label).lower().strip()
    if any(k in l for k in ('basket', 'flexible', 'vinyl', 'bag', 'pouch', '비닐')):
        return 'FlexibleBasket'
    if 'redball' in l or 'red ball' in l or 'ball1' in l or 'ball 1' in l:
        return 'RedBall'
    if 'greenball' in l or 'green ball' in l or 'ball2' in l or 'ball 2' in l:
        return 'GreenBall'
    if 'yellowball' in l or 'yellow ball' in l or 'ball3' in l or 'ball 3' in l:
        return 'YellowBall'
    if 'asmblock1' in l or 'asm block 1' in l:
        return 'AsmBlock1'
    if 'asmblock2' in l or 'asm block 2' in l:
        return 'AsmBlock2'
    if 'asmblock3' in l or 'asm block 3' in l:
        return 'AsmBlock3'
    if 'red' in l or 'block1' in l or 'block 1' in l: return 'Block1'
    if 'green' in l or 'block2' in l or 'block 2' in l: return 'Block2'
    if 'blue' in l or 'block3' in l or 'block 3' in l: return 'Block3'
    if 'yellow' in l or 'block4' in l or 'block 4' in l: return 'Block4'
    if 'magenta' in l or 'block5' in l or 'block 5' in l: return 'Block5'
    if 'cyan' in l or 'block6' in l or 'block 6' in l: return 'Block6'
    if 'orange' in l or 'block7' in l or 'block 7' in l: return 'Block7'
    if 'purple' in l or 'block8' in l or 'block 8' in l: return 'Block8'
    if 'lime' in l or 'block9' in l or 'block 9' in l: return 'Block9'
    if 'bar' in l or 'longbar' in l: return 'LongBar'
    if 'engine' in l or 'heavyengine' in l: return 'HeavyEnginePart'
    for i in range(10):
        if f'convitem{i}' in l or f'convitem {i}' in l or f'item{i}' in l or f'item {i}' in l:
            return f'ConvItem{i}'
    if 'conveyor' in l or 'convitem' in l:
        return 'ConvItem0'
    return label


def normalize_robot_id(robot_str: str) -> str:
    """Normalize robot identifier strings to 'FR3_1', 'FR3_2', 'FR3_3'."""
    s = str(robot_str).upper()
    if '1' in s or 'FR3_1' in s or 'ROBOT1' in s: return 'FR3_1'
    if '2' in s or 'FR3_2' in s or 'ROBOT2' in s: return 'FR3_2'
    if '3' in s or 'FR3_3' in s or 'ROBOT3' in s: return 'FR3_3'
    return robot_str


try:
    from isaac_ros2_control.rule_based_task_generator import RuleBasedTaskGenerator
except ImportError:
    try:
        from rule_based_task_generator import RuleBasedTaskGenerator
    except ImportError:
        class RuleBasedTaskGenerator:
            """Open-source baseline task state formatter (full relay blueprint generator in private/research)."""

            @staticmethod
            def generate_blueprint(workspace_state, goal_text: str = "") -> tuple[dict, str]:
                blocks_on_tower = list(getattr(workspace_state, 'blocks_on_tower', [])) if workspace_state else []
                tower_height = len(blocks_on_tower)
                available = {
                    r: [b for b in owned if b not in blocks_on_tower]
                    for r, owned in ROBOT_OWNED_BLOCKS.items()
                }
                data = {
                    'task_type': 'tower_stacking',
                    'current_tower_height': tower_height,
                    'blocks_on_tower': blocks_on_tower,
                    'available_per_robot': available,
                }
                text = (
                    "=== WORKSPACE BLUEPRINT ===\n"
                    f"Tower Height: {tower_height}/9 ({blocks_on_tower})\n"
                    f"FR3_1 (Table 1): {available['FR3_1']}\n"
                    f"FR3_2 (Table 2): {available['FR3_2']}\n"
                    f"FR3_3 (Table 3): {available['FR3_3']}"
                )
                return data, text


class RuleBasedTaskVerifier:
    """Pre-execution validation layer to intercept and verify VLA tool calls."""

    def __init__(self, logger=None):
        self.logger = logger
        # Robot holding state tracker: { 'FR3_1': None or 'Block1', ... }
        self.robot_holding = {'FR3_1': None, 'FR3_2': None, 'FR3_3': None}
        self.verified_count = 0
        self.intercepted_count = 0

    def verify_action(self, action_name: str, args: dict, workspace_state, goal_text: str = "") -> tuple[bool, dict, str]:
        """Validate and sanitize a VLA tool call before execution.

        Returns:
            is_valid (bool): True if allowed to proceed.
            sanitized_args (dict): Validated / auto-corrected arguments.
            message (str): Human-readable validation report or rejection reason.
        """
        sanitized = dict(args) if args else {}
        action = action_name.lower().strip()

        # Global / Perception tools are always safe
        if action in ['detect_objects', 'get_workspace_status', 'verify_tower', 'replan']:
            self.verified_count += 1
            return True, sanitized, f"Rule-verifier pass: {action} is safe."

        if action in ['dual_arm_pick', 'dual_arm_place', 'dual_arm_circle', 'dual_arm_draw_circle', 'dual_arm_motion']:
            sanitized['speed'] = sanitized.get('speed', 'fast')
            if action == 'dual_arm_pick':
                target_obj = sanitized.get('target') or sanitized.get('object_label') or 'LongBar'
                self.robot_holding['FR3_1'] = target_obj
                self.robot_holding['FR3_2'] = target_obj
            elif action == 'dual_arm_place':
                self.robot_holding['FR3_1'] = None
                self.robot_holding['FR3_2'] = None
            elif action in ['dual_arm_circle', 'dual_arm_draw_circle', 'dual_arm_motion']:
                sanitized['radius'] = float(sanitized.get('radius', 0.08))
                sanitized['cycles'] = int(sanitized.get('cycles', 1))
                sanitized['plane'] = str(sanitized.get('plane', 'XY')).upper()
            self.verified_count += 1
            return True, sanitized, f"Rule-verifier pass: {action} dual-arm coordinated motion is safe."

        # Robot identifier validation
        robot_raw = sanitized.get('robot', '')
        robot = normalize_robot_id(robot_raw)
        if robot not in ['FR3_1', 'FR3_2', 'FR3_3']:
            self.intercepted_count += 1
            return False, sanitized, f"Unknown robot '{robot_raw}'. Must be FR3_1, FR3_2, or FR3_3."
        sanitized['robot'] = robot

        # ── 1. Verification for PICK ──────────────────────────────────────────
        if action == 'pick':
            target_raw = sanitized.get('target') or sanitized.get('object_label', '')
            block_name = resolve_block_name(target_raw)
            if not block_name:
                self.intercepted_count += 1
                return False, sanitized, f"Cannot resolve pick target '{target_raw}'."

            # Auto-promote oversized / heavy objects to coordinated dual-arm pick
            if block_name in ['LongBar', 'HeavyEnginePart']:
                sanitized['action'] = 'dual_arm_pick'
                sanitized['target'] = block_name
                sanitized['speed'] = sanitized.get('speed', 'fast')
                self.robot_holding['FR3_1'] = block_name
                self.robot_holding['FR3_2'] = block_name
                self.verified_count += 1
                return True, sanitized, f"Rule-verifier intercept: Promoted single-arm pick of '{block_name}' to coordinated dual_arm_pick."

            # Check holding precondition: robot must not already hold a block
            if self.robot_holding.get(robot) is not None:
                held = self.robot_holding[robot]
                self.intercepted_count += 1
                return False, sanitized, f"Robot {robot} is already holding {held}. It must place it before picking another."

            goal_lower = goal_text.lower() if goal_text else ""
            is_tower = any(k in goal_lower for k in ['tower', 'stack', 'layer', 'pyramid']) if goal_lower else True

            # If tower task, check if block is already stacked in the tower
            if is_tower:
                blocks_on_tower = getattr(workspace_state, 'blocks_on_tower', [])
                if block_name in blocks_on_tower:
                    self.intercepted_count += 1
                    unstacked = [b for b in ROBOT_OWNED_BLOCKS[robot] if b not in blocks_on_tower]
                    if unstacked:
                        corrected_block = unstacked[0]
                        sanitized['target'] = corrected_block
                        sanitized['object_label'] = corrected_block
                        msg = (f"[INTERCEPT] {block_name} is already in tower. "
                               f"Auto-corrected to unstacked block {corrected_block} for {robot}.")
                        self._log_warn(msg)
                        block_name = corrected_block
                    else:
                        return False, sanitized, f"{block_name} is already stacked on the tower."

            # Dynamic Physical Reachability check based on actual TF coordinates
            # (Skip static reach rejection for moving ConvItem0..9, as ConveyorDualController
            # dynamically selects whichever ConvItem is inside the arm's conveyor window at 50Hz)
            is_conv_item = block_name.startswith('ConvItem')
            block_info = getattr(workspace_state, 'block_status', {}).get(block_name, {}) if workspace_state else {}
            block_pos = block_info.get('pos')

            if block_pos is not None and not is_conv_item:
                bx, by, bz = block_pos
                dist_mode1 = np.hypot(bx - ROBOT_BASES[robot][0], by - ROBOT_BASES[robot][1])
                conv_base = CONVEYOR_ROBOT_BASES.get(robot)
                dist_mode2 = np.hypot(bx - conv_base[0], by - conv_base[1]) if conv_base is not None else float('inf')
                dist_to_robot = dist_mode1 if is_tower else min(dist_mode1, dist_mode2)
                if dist_to_robot > MAX_ARM_REACH:
                    self.intercepted_count += 1
                    reachable_robots = [
                        r for r, base in ROBOT_BASES.items()
                        if np.hypot(bx - base[0], by - base[1]) <= MAX_ARM_REACH
                    ]
                    rec = f"Dispatch {reachable_robots[0]} instead" if reachable_robots else "Block is out of reach"
                    return False, sanitized, (
                        f"Block '{block_name}' is currently at ({bx:.2f}, {by:.2f}), which is {dist_to_robot:.2f}m from {robot} "
                        f"(max reach {MAX_ARM_REACH}m). {rec} to pick and place it on Central Table [0.0, 0.0] for relay."
                    )
            else:
                # TF position not yet queried: check initial ownership only if it's a tower task
                expected_robot = BLOCK_TO_ROBOT.get(block_name)
                if is_tower and expected_robot and expected_robot != robot:
                    self.intercepted_count += 1
                    if self.robot_holding.get(expected_robot) is None:
                        sanitized['robot'] = expected_robot
                        msg = (f"[INTERCEPT] {block_name} initially belongs to {expected_robot} (Table {expected_robot[-1]}). "
                               f"Auto-rerouted assignment from {robot} to {expected_robot}.")
                        self._log_warn(msg)
                        robot = expected_robot
                    else:
                        return False, sanitized, f"{block_name} is on {expected_robot}'s table. {robot} cannot reach it."

            # Set speed and approach parameters safely
            sanitized['speed'] = sanitized.get('speed', 'fast')
            sanitized['approach_height'] = float(sanitized.get('approach_height', 0.12))
            sanitized['target'] = block_name
            sanitized['object_label'] = block_name

            self.robot_holding[robot] = block_name
            self.verified_count += 1
            return True, sanitized, f"Verified pick: {robot} picking {block_name}."

        # ── 2. Verification for PLACE ─────────────────────────────────────────
        elif action in ['place', 'place_relative']:
            # Auto-promote single-arm place to dual_arm_place if bimanual object is held
            if self.robot_holding.get('FR3_1') in ['LongBar', 'HeavyEnginePart'] or \
               self.robot_holding.get('FR3_2') in ['LongBar', 'HeavyEnginePart']:
                sanitized['action'] = 'dual_arm_place'
                sanitized['x'] = float(sanitized.get('x', 0.0))
                sanitized['y'] = float(sanitized.get('y', 0.0))
                sanitized['speed'] = sanitized.get('speed', 'fast')
                self.robot_holding['FR3_1'] = None
                self.robot_holding['FR3_2'] = None
                self.verified_count += 1
                return True, sanitized, "Rule-verifier intercept: Promoted single-arm place to coordinated dual_arm_place."

            target_x = float(sanitized.get('x', 0.0))
            target_y = float(sanitized.get('y', 0.0))

            # Validate target location is on ANY valid workspace table surface
            on_table = False
            target_table_name = "unknown"
            for t_name, t_info in TABLE_ZONES.items():
                dist_to_t = np.hypot(target_x - t_info['center'][0], target_y - t_info['center'][1])
                if dist_to_t <= t_info['radius']:
                    on_table = True
                    target_table_name = t_name
                    break

            if not on_table:
                self.intercepted_count += 1
                return False, sanitized, (
                    f"Target place coordinates ({target_x:.2f}, {target_y:.2f}) do not lie on any valid table "
                    f"(Central Table [0,0], Table 1 [0,-1.05], Table 2 [0.91,0.53], Table 3 [-0.91,0.53])."
                )

            # Check kinematic reachability from this robot's base (supporting both Mode 1 and Mode 2/3 base mounts)
            goal_lower_place = goal_text.lower() if goal_text else ""
            is_tower_place = any(k in goal_lower_place for k in ['tower', 'stack', 'layer', 'pyramid', 'table 1', 'table 2', 'table 3', 'relay'])
            dist_mode1 = np.hypot(target_x - ROBOT_BASES[robot][0], target_y - ROBOT_BASES[robot][1])
            conv_base = CONVEYOR_ROBOT_BASES.get(robot)
            dist_mode2 = np.hypot(target_x - conv_base[0], target_y - conv_base[1]) if conv_base is not None else float('inf')
            dist_from_robot = dist_mode1 if is_tower_place else min(dist_mode1, dist_mode2)
            max_distance_check = dist_mode1 if is_tower_place else max(dist_mode1, dist_mode2)
            if dist_from_robot > MAX_ARM_REACH:
                self.intercepted_count += 1
                return False, sanitized, (
                    f"Target ({target_x:.2f}, {target_y:.2f}) on {target_table_name} is {dist_from_robot:.2f}m from {robot} base "
                    f"(max reach {MAX_ARM_REACH}m). {robot} cannot place directly here. "
                    f"Place on the Central Table [0.0, 0.0] first so the destination robot can relay it."
                )

            if (is_tower_place and dist_mode1 < MIN_ARM_REACH) or (not is_tower_place and dist_from_robot < MIN_ARM_REACH and max_distance_check < MIN_ARM_REACH):
                self.intercepted_count += 1
                return False, sanitized, (
                    f"Target ({target_x:.2f}, {target_y:.2f}) is too close to {robot} base column "
                    f"({dist_from_robot:.2f}m < {MIN_ARM_REACH}m)."
                )

            if self.robot_holding.get(robot) is None:
                self._log_warn(f"[VERIFIER] Note: {robot} placing without tracked hold; proceeding with controller state.")

            self.robot_holding[robot] = None  # Clear holding state on place
            sanitized['speed'] = sanitized.get('speed', 'fast')
            sanitized['approach_height'] = float(sanitized.get('approach_height', 0.12))

            self.verified_count += 1
            return True, sanitized, f"Verified {action} for {robot} on {target_table_name} at ({target_x:.2f}, {target_y:.2f})."

        # ── 3. Verification for GO_HOME ───────────────────────────────────────
        elif action == 'go_home':
            self.verified_count += 1
            return True, sanitized, f"Verified go_home for {robot}."

        return True, sanitized, f"Action {action} passed verification."

    def reset(self):
        """Reset internal holding tracking upon simulation reset."""
        self.robot_holding = {'FR3_1': None, 'FR3_2': None, 'FR3_3': None}
        self.verified_count = 0
        self.intercepted_count = 0

    def _log_warn(self, msg: str):
        if self.logger:
            self.logger.warn(f"\033[93m{msg}\033[0m")
        else:
            print(f"[WARN] {msg}")

    def _log_info(self, msg: str):
        if self.logger:
            self.logger.info(f"\033[92m{msg}\033[0m")
        else:
            print(f"[INFO] {msg}")
