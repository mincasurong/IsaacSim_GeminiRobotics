#!/usr/bin/env python3
"""
Unit Test Suite for Rule-Based Task Generator and Safety Verifier.

Verifies:
- Label resolution and robot normalization
- Pre-execution validation of pick & place tool calls
- Auto-promotion of oversized/heavy objects (LongBar) to dual_arm_pick
- Holding precondition enforcement (no double picks)
- Boundary checks and auto-correction of out-of-bounds placements
- Blueprint sequence generation
"""

import os
import sys
import unittest
import numpy as np

# Ensure module is discoverable under test execution
pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)

from isaac_ros2_control.rule_based_verifier import (
    resolve_block_name,
    normalize_robot_id,
    RuleBasedTaskGenerator,
    RuleBasedTaskVerifier,
    ROBOT_OWNED_BLOCKS,
)


class MockWorkspaceState:
    """Mock representation of workspace state for unit tests without live ROS."""

    def __init__(self):
        self.blocks_on_tower = []
        self.tower_height = 0
        self.holding = {'FR3_1': None, 'FR3_2': None, 'FR3_3': None}
        self.block_status = {
            'Block1': {'pos': np.array([0.0, -1.0, 0.35]), 'held_by': None},
            'Block2': {'pos': np.array([0.0, -1.1, 0.35]), 'held_by': None},
            'Block3': {'pos': np.array([0.0, -1.2, 0.35]), 'held_by': None},
            'Block4': {'pos': np.array([0.85, 0.5, 0.35]), 'held_by': None},
            'Block5': {'pos': np.array([0.90, 0.55, 0.35]), 'held_by': None},
            'Block6': {'pos': np.array([0.95, 0.60, 0.35]), 'held_by': None},
            'Block7': {'pos': np.array([-0.85, 0.5, 0.35]), 'held_by': None},
            'Block8': {'pos': np.array([-0.90, 0.55, 0.35]), 'held_by': None},
            'Block9': {'pos': np.array([-0.95, 0.60, 0.35]), 'held_by': None},
        }

    def get_summary(self):
        return {
            'tower': {'layers': self.tower_height, 'blocks': self.blocks_on_tower},
            'robots': self.holding,
        }


class TestRuleBasedVerifier(unittest.TestCase):
    """Test suite for deterministic task generation and VLA safety verifier."""

    def setUp(self):
        self.verifier = RuleBasedTaskVerifier()
        self.generator = RuleBasedTaskGenerator()
        self.ws = MockWorkspaceState()

    def test_resolve_block_name(self):
        """Verify natural language object labels map to canonical prim identifiers."""
        self.assertEqual(resolve_block_name("Red Cube"), "Block1")
        self.assertEqual(resolve_block_name("Green Cylinder"), "Block2")
        self.assertEqual(resolve_block_name("Blue Cube"), "Block3")
        self.assertEqual(resolve_block_name("yellow cylinder"), "Block4")
        self.assertEqual(resolve_block_name("magenta cube"), "Block5")
        self.assertEqual(resolve_block_name("cyan cylinder"), "Block6")
        self.assertEqual(resolve_block_name("LongBar"), "LongBar")
        self.assertEqual(resolve_block_name("heavy engine part"), "HeavyEnginePart")
        self.assertEqual(resolve_block_name("ConvItem3"), "ConvItem3")

    def test_normalize_robot_id(self):
        """Verify heterogeneous robot identifiers normalize to standard FR3 keys."""
        self.assertEqual(normalize_robot_id("1"), "FR3_1")
        self.assertEqual(normalize_robot_id("robot1"), "FR3_1")
        self.assertEqual(normalize_robot_id("FR3_1"), "FR3_1")
        self.assertEqual(normalize_robot_id("2"), "FR3_2")
        self.assertEqual(normalize_robot_id("robot3"), "FR3_3")

    def test_auto_promotion_long_bar(self):
        """Verify picking LongBar or HeavyEnginePart is auto-promoted to dual_arm_pick."""
        raw_args = {"robot": "FR3_1", "object_label": "LongBar"}
        is_valid, sanitized, msg = self.verifier.verify_action(
            "pick", raw_args, self.ws, goal_text="Build tower"
        )
        self.assertTrue(is_valid)
        self.assertEqual(sanitized.get("action"), "dual_arm_pick")
        self.assertEqual(sanitized.get("target"), "LongBar")
        self.assertIn("Promoted single-arm pick", msg)

    def test_holding_precondition_blocks_double_pick(self):
        """Verify a robot already holding an object cannot execute a second pick."""
        # Pick Block1 with FR3_1
        is_valid, sanitized, msg = self.verifier.verify_action(
            "pick", {"robot": "FR3_1", "object_label": "Block1"}, self.ws
        )
        self.assertTrue(is_valid)

        # Attempt to pick Block2 while FR3_1 is still holding Block1
        is_valid2, sanitized2, msg2 = self.verifier.verify_action(
            "pick", {"robot": "FR3_1", "object_label": "Block2"}, self.ws
        )
        self.assertFalse(is_valid2)
        self.assertIn("already holding", msg2)

    def test_place_boundary_enforcement(self):
        """Verify placing outside workspace table boundaries or beyond max reach is rejected."""
        # Target coordinates completely outside any table zone (5.0, 5.0)
        is_valid_far, _, msg_far = self.verifier.verify_action(
            "place", {"robot": "FR3_2", "x": 5.0, "y": 5.0}, self.ws
        )
        self.assertFalse(is_valid_far)
        self.assertIn("do not lie on any valid table", msg_far)

        # Target on Table 1 (0.0, -1.05) is out of reach for FR3_2 (located at 0.39, 0.23)
        is_valid_reach, _, msg_reach = self.verifier.verify_action(
            "place", {"robot": "FR3_2", "x": 0.0, "y": -1.05}, self.ws
        )
        self.assertFalse(is_valid_reach)
        self.assertIn("max reach", msg_reach)

    def test_place_success_clears_holding_state(self):
        """Verify valid place action clears the robot holding record."""
        # Pick Block4 with FR3_2
        self.verifier.verify_action("pick", {"robot": "FR3_2", "object_label": "Block4"}, self.ws)
        self.assertEqual(self.verifier.robot_holding["FR3_2"], "Block4")

        # Place Block4 on target table (0.0, 0.0)
        is_valid, sanitized, msg = self.verifier.verify_action(
            "place", {"robot": "FR3_2", "x": 0.0, "y": 0.0}, self.ws
        )
        self.assertTrue(is_valid)
        self.assertIsNone(self.verifier.robot_holding["FR3_2"])

    def test_dual_arm_primitives_pass_verification(self):
        """Verify dual-arm primitives are validated and sanitized properly."""
        is_valid, sanitized, msg = self.verifier.verify_action(
            "dual_arm_circle", {"radius": 0.08, "cycles": 2, "plane": "xy"}, self.ws
        )
        self.assertTrue(is_valid)
        self.assertEqual(sanitized["plane"], "XY")
        self.assertEqual(sanitized["cycles"], 2)

    def test_task_generator_blueprint_generation(self):
        """Verify RuleBasedTaskGenerator generates a well-structured deterministic blueprint."""
        plan_dict, blueprint_text = self.generator.generate_blueprint(self.ws, "Build a 9-layer tower")
        self.assertIsInstance(plan_dict, dict)
        self.assertIsInstance(blueprint_text, str)
        self.assertIn("BLUEPRINT", blueprint_text.upper())
        self.assertIn("FR3_1", blueprint_text)
        self.assertIn("FR3_2", blueprint_text)
        self.assertIn("FR3_3", blueprint_text)


if __name__ == '__main__':
    unittest.main()
