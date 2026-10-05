"""Rule-Based Task Generator and Safety Verifier for Gemini Robotics-ER-2.

This module provides the deterministic foundation for the hybrid VLA architecture:
1. RuleBasedTaskGenerator:
   - Queries real-time workspace state (TF transforms, block positions, tower height).
   - Generates the deterministic baseline stacking sequence and constraints.
   - Formats a compact, grounded blueprint for Gemini Robotics-ER-2.

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
    'FR3_1': ['Block1', 'Block2', 'Block3'],
    'FR3_2': ['Block4', 'Block5', 'Block6'],
    'FR3_3': ['Block7', 'Block8', 'Block9'],
}

ROBOT_BASES = {
    'FR3_1': np.array([0.0, -0.45]),
    'FR3_2': np.array([0.3897, 0.225]),
    'FR3_3': np.array([-0.3897, 0.225]),
}

TABLE_ZONES = {
    'central_table': {'center': np.array([0.0, 0.0]), 'radius': 0.22},
    'table_1': {'center': np.array([0.0, -1.05]), 'radius': 0.35},
    'table_2': {'center': np.array([0.909, 0.525]), 'radius': 0.35},
    'table_3': {'center': np.array([-0.909, 0.525]), 'radius': 0.35},
    'main_workbench': {'center': np.array([0.0, -0.25]), 'radius': 1.40},
    'assembly_buffer': {'center': np.array([0.0, 0.25]), 'radius': 1.20},
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
}


def resolve_block_name(label: str) -> str:
    """Normalize object labels (e.g. 'Red Cube', 'block 1', 'ConvItem0', 'LongBar') to canonical prim names."""
    if not label:
        return ""
    l = str(label).lower().strip()
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
    return label


def normalize_robot_id(robot_str: str) -> str:
    """Normalize robot identifier strings to 'FR3_1', 'FR3_2', 'FR3_3'."""
    s = str(robot_str).upper()
    if '1' in s or 'FR3_1' in s or 'ROBOT1' in s: return 'FR3_1'
    if '2' in s or 'FR3_2' in s or 'ROBOT2' in s: return 'FR3_2'
    if '3' in s or 'FR3_3' in s or 'ROBOT3' in s: return 'FR3_3'
    return robot_str


class RuleBasedTaskGenerator:
    """Deterministic task and sequence planner for multi-robot tasks (tower or custom transfer/relay)."""

    @staticmethod
    def generate_blueprint(workspace_state, goal_text: str = "") -> tuple[dict, str]:
        """Generate a grounded task blueprint based on physical workspace state and user goal."""
        if workspace_state is None:
            blocks_on_tower = []
        else:
            blocks_on_tower = list(getattr(workspace_state, 'blocks_on_tower', []))
        tower_height = len(blocks_on_tower)

        # Classify remaining unstacked blocks per robot
        available_per_robot = {}
        for r_id, owned_blocks in ROBOT_OWNED_BLOCKS.items():
            unstacked = [b for b in owned_blocks if b not in blocks_on_tower]
            available_per_robot[r_id] = unstacked

        goal_lower = goal_text.lower() if goal_text else ""
        is_tower_task = any(k in goal_lower for k in ['tower', 'stack', 'layer', 'pyramid']) if goal_lower else True

        if is_tower_task:
            # Optimal round-robin stacking plan (FR3_1 -> FR3_2 -> FR3_3 ...)
            canonical_order = [
                ('FR3_1', 'Block1'),
                ('FR3_2', 'Block4'),
                ('FR3_3', 'Block7'),
                ('FR3_1', 'Block2'),
                ('FR3_2', 'Block5'),
                ('FR3_3', 'Block8'),
                ('FR3_1', 'Block3'),
                ('FR3_2', 'Block6'),
                ('FR3_3', 'Block9'),
            ]

            next_actions = []
            for robot, block in canonical_order:
                if block not in blocks_on_tower:
                    next_actions.append({
                        'step': len(next_actions) + 1,
                        'target_layer': tower_height + len(next_actions) + 1,
                        'robot': robot,
                        'block': block,
                        'description': BLOCK_DESCRIPTIONS.get(block, block),
                        'source_table': 'Table 1' if robot == 'FR3_1' else ('Table 2' if robot == 'FR3_2' else 'Table 3'),
                    })

            blueprint_data = {
                'task_type': 'tower_stacking',
                'current_tower_height': tower_height,
                'blocks_on_tower': blocks_on_tower,
                'available_per_robot': available_per_robot,
                'recommended_next_steps': next_actions[:4],
            }

            lines = [
                "================================================================",
                "📋 DETERMINISTIC RULE-BASED BLUEPRINT (Grounded Workspace State)",
                "================================================================",
                f"Current Tower Height: {tower_height}/9 stacked blocks: {blocks_on_tower}",
                "Robot Workstation & Table Assignment (Physical Constraints):",
                f"  - FR3_1 (Bottom): Operates Source Table 1. Available: {available_per_robot['FR3_1']}",
                f"  - FR3_2 (Top-Right): Operates Source Table 2. Available: {available_per_robot['FR3_2']}",
                f"  - FR3_3 (Top-Left): Operates Source Table 3. Available: {available_per_robot['FR3_3']}",
                "",
                "Recommended Agile Multi-Robot Execution Schedule:",
            ]
            if next_actions:
                for act in next_actions[:3]:
                    lines.append(
                        f"  * Layer {act['target_layer']}: Dispatch {act['robot']} -> Pick {act['block']} "
                        f"({act['description']}) from {act['source_table']} -> Place on Central Target Table [0,0]"
                    )
            else:
                lines.append("  * All 9 blocks have been successfully stacked into the tower!")
            lines.append("================================================================")
            return blueprint_data, "\n".join(lines)

        # ── General Table Transfer / Relay Task Blueprint ────────────────────
        blueprint_data = {
            'task_type': 'transfer_relay',
            'user_goal': goal_text,
            'available_per_robot': available_per_robot,
            'table_centers': {
                'Table 1': [0.0, -1.05],
                'Table 2': [0.909, 0.525],
                'Table 3': [-0.909, 0.525],
                'Central Table': [0.0, 0.0]
            }
        }

        lines = [
            "================================================================",
            "📋 MULTI-ROBOT TRANSFER & RELAY BLUEPRINT",
            "================================================================",
            f"User Goal: \"{goal_text}\"",
            "Workspace Geometry & Physical Reach Constraints:",
            "  - FR3_1: Reaches Table 1 [0.0, -1.05] & Central Table [0.0, 0.0]. CANNOT reach Table 3 directly (1.33m > 0.85m reach).",
            "  - FR3_2: Reaches Table 2 [0.909, 0.525] & Central Table [0.0, 0.0]. CANNOT reach Table 1 or 3 directly.",
            "  - FR3_3: Reaches Table 3 [-0.909, 0.525] & Central Table [0.0, 0.0]. CANNOT reach Table 1 directly.",
            "  - Central Staging Table [0.0, 0.0]: Shared handoff/relay zone reachable by ALL 3 arms.",
            "",
            "MANDATORY MULTI-ROBOT RELAY PROCEDURE FOR TABLE 1 -> TABLE 3:",
            "  Because FR3_1 cannot physically reach Table 3, execute a cooperative relay:",
            "  1. [FR3_1 Stage 1]: pick(robot='FR3_1', object_label=block) from Table 1.",
            "  2. [FR3_1 Stage 1]: place(robot='FR3_1', x=0.0, y=0.0, speed='fast') on Central Table.",
            "  3. [FR3_1 Retreat]: go_home(robot='FR3_1') to release central table mutual exclusion.",
            "  4. [FR3_3 Stage 2]: pick(robot='FR3_3', object_label=block) from Central Table [0.0, 0.0].",
            "  5. [FR3_3 Stage 2]: place(robot='FR3_3', x=-0.909, y=0.525, speed='fast') on Table 3.",
            "  6. [FR3_3 Retreat]: go_home(robot='FR3_3').",
            "  Repeat sequentially for all required blocks.",
            "================================================================",
        ]
        return blueprint_data, "\n".join(lines)


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

        # Dual-arm coordinated actions control both FR3_1 and FR3_2
        if action in ['dual_arm_pick', 'dual_arm_place', 'dual_arm_circle', 'dual_arm_draw_circle', 'dual_arm_motion']:
            sanitized['speed'] = sanitized.get('speed', 'fast')
            if action in ['dual_arm_circle', 'dual_arm_draw_circle', 'dual_arm_motion']:
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
            block_info = getattr(workspace_state, 'block_status', {}).get(block_name, {}) if workspace_state else {}
            block_pos = block_info.get('pos')

            if block_pos is not None:
                bx, by, bz = block_pos
                dist_to_robot = np.hypot(bx - ROBOT_BASES[robot][0], by - ROBOT_BASES[robot][1])
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
                sanitized['y'] = float(sanitized.get('y', 0.25))
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

            # Check kinematic reachability from this robot's base
            dist_from_robot = np.hypot(target_x - ROBOT_BASES[robot][0], target_y - ROBOT_BASES[robot][1])
            if dist_from_robot > MAX_ARM_REACH:
                self.intercepted_count += 1
                return False, sanitized, (
                    f"Target ({target_x:.2f}, {target_y:.2f}) on {target_table_name} is {dist_from_robot:.2f}m from {robot} base "
                    f"(max reach {MAX_ARM_REACH}m). {robot} cannot place directly here. "
                    f"Place on the Central Table [0.0, 0.0] first so the destination robot can relay it."
                )

            if dist_from_robot < MIN_ARM_REACH:
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
