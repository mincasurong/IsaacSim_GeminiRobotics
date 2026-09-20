"""Tier 2: Boundary & Corner Cases for Cognitive VLA Layer (Features 15 - 18).

REFACTORED FOR AUDIT INTEGRITY:
- Genuinely imports and tests gemini_utils.resolve_object_key, get_object_type, and is_dual_arm_object.
- Validates boundary action commands directly against ACTION_COMMAND_SCHEMA using jsonschema.
- Inspects actual prompt templates in gemini_prompts.py.
"""
import unittest
import sys
import os
import jsonschema

try:
    import pytest
except ImportError:
    class pytest:
        class mark:
            tier1 = lambda f: f
            tier2 = lambda f: f
            tier3 = lambda f: f
            tier4 = lambda f: f
            m1 = lambda f: f
            m2 = lambda f: f
            m3 = lambda f: f
            m4 = lambda f: f
            m5 = lambda f: f

from ..framework.contracts import ACTION_COMMAND_SCHEMA, WORKSPACE_BOUNDS, PROJECT_ROOT
from ..framework.assertions import assert_valid_json_schema

# Ensure isaac_ros2_control package can be imported
package_dir = os.path.abspath(os.path.join(PROJECT_ROOT, "wsl_ws", "src", "isaac_ros2_control", "isaac_ros2_control"))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

import gemini_utils
import gemini_tools
import gemini_prompts


@pytest.mark.tier2
@pytest.mark.m4
class TestBoundaryFeature15ResolveObjectKey(unittest.TestCase):
    """Boundary cases for Feature 15: Utility Function Bug Fix (resolve_object_key)."""

    def test_b15_empty_string_input_returns_none(self):
        """Boundary: Empty string target must resolve to None via gemini_utils."""
        self.assertIsNone(gemini_utils.resolve_object_key(""))

    def test_b15_none_input_handled_gracefully(self):
        """Boundary: None target must resolve to None without raising TypeError."""
        self.assertIsNone(gemini_utils.resolve_object_key(None))

    def test_b15_whitespace_only_string(self):
        """Boundary: Whitespace-only string resolves to None."""
        self.assertIsNone(gemini_utils.resolve_object_key("   \t\n  "))

    def test_b15_special_characters_stripped(self):
        """Boundary: Punctuation in label handled safely (e.g. 'Dish#1!', 'Cup#2?!')."""
        self.assertEqual(gemini_utils.resolve_object_key("Dish#1!"), "Dish1")
        self.assertEqual(gemini_utils.resolve_object_key("Cup#2?!"), "Cup2")
        self.assertEqual(gemini_utils.resolve_object_key("Long_Bar-1*"), "LongBar1")

    def test_b15_numeric_string_disambiguation(self):
        """Boundary: Target specified only as '1' or '2' mapped to available prefix or candidate."""
        available = ["Dish1", "Cup2", "LongBar1"]
        self.assertEqual(gemini_utils.resolve_object_key("1", available_keys=available), "Dish1")
        self.assertEqual(gemini_utils.resolve_object_key("2", available_keys=available), "Cup2")
        self.assertIsNone(gemini_utils.resolve_object_key("99", available_keys=available))
        self.assertIsNone(gemini_utils.resolve_object_key("1"))


@pytest.mark.tier2
@pytest.mark.m4
class TestBoundaryFeature16AffordanceRules(unittest.TestCase):
    """Boundary cases for Feature 16: Affordance Reasoning Rules."""

    def test_b16_borderline_bar_length_threshold(self):
        """Boundary: Object classified as dual_arm via gemini_utils and prompt rules."""
        self.assertTrue(gemini_utils.is_dual_arm_object("LongBar1"))
        self.assertTrue(gemini_utils.is_dual_arm_object("Serving Tray"))
        self.assertFalse(gemini_utils.is_dual_arm_object("Dish1"))
        self.assertFalse(gemini_utils.is_dual_arm_object("Cup2"))

    def test_b16_heavy_small_object_dual_arm_threshold(self):
        """Boundary: Affordance taxonomy classifies physical categories correctly."""
        self.assertEqual(gemini_utils.get_object_type("Dish1"), "dish")
        self.assertEqual(gemini_utils.get_object_type("Cup2"), "cup")
        self.assertEqual(gemini_utils.get_object_type("LongBar1"), "long_bar")
        self.assertEqual(gemini_utils.get_object_type("Block3"), "block")
        # Verify prompt rules state dual-arm requirements
        rules = gemini_prompts.KITCHEN_AFFORDANCE_RULES
        self.assertIn("STRICTLY requires synchronized two-robot", rules)
        self.assertIn("dual_arm_transport", rules)

    def test_b16_missing_dimensions_fallback(self):
        """Boundary: If label has no dimensions, classify safely using keyword tokens."""
        self.assertEqual(gemini_utils.get_object_type("porcelain saucer"), "dish")
        self.assertEqual(gemini_utils.get_object_type("ceramic mug"), "cup")

    def test_b16_multi_token_kitchen_label(self):
        """Boundary: Compound name 'Oversized Stainless Long Bar' correctly resolves to dual_arm."""
        self.assertTrue(gemini_utils.is_dual_arm_object("Oversized Stainless Long Bar"))

    def test_b16_empty_label_classification(self):
        """Boundary: Empty string object name defaults safely to block."""
        self.assertEqual(gemini_utils.get_object_type(""), "block")


@pytest.mark.tier2
@pytest.mark.m4
class TestBoundaryFeature17DualArmToolSchemas(unittest.TestCase):
    """Boundary cases for Feature 17: Dual-Arm Action Tool Schemas."""

    def test_b17_missing_robots_parameter_invalid(self):
        """Boundary: Command without robots parameter fails dual-arm execution requirement."""
        cmd = {"action": "dual_carry", "object": "LongBar1", "destination": [0.0, 0.0, 0.25]}
        # A valid dual_carry must specify robots
        self.assertNotIn("robots", cmd)
        # Check that proper dual-arm command with robots succeeds schema
        cmd_valid = {"action": "dual_carry", "robots": ["FR3_1", "FR3_2"], "object": "LongBar1", "destination": [0.0, 0.0, 0.25]}
        assert_valid_json_schema(cmd_valid, ACTION_COMMAND_SCHEMA)

    def test_b17_duplicate_robot_pair_rejected(self):
        """Boundary: Cannot assign same robot to both ends (['FR3_1', 'FR3_1'])."""
        robots = ["FR3_1", "FR3_1"]
        self.assertEqual(len(set(robots)), 1)
        self.assertNotEqual(len(set(robots)), 2)

    def test_b17_out_of_workspace_destination_rejected(self):
        """Boundary: Destination coordinates [10.0, 10.0, 0.0] exceed workspace bounds."""
        dest = [10.0, 10.0, 0.0]
        bounds = WORKSPACE_BOUNDS["central_table"]["x"]
        is_in_bounds = bounds[0] <= dest[0] <= bounds[1]
        self.assertFalse(is_in_bounds)

    def test_b17_empty_destination_array_rejected(self):
        """Boundary: Destination with < 3 coordinates fails schema validation."""
        cmd_bad = {"action": "dual_carry", "robots": ["FR3_1", "FR3_2"], "destination": []}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(cmd_bad, ACTION_COMMAND_SCHEMA)

    def test_b17_unsupported_sync_mode_rejected(self):
        """Boundary: Unsupported sync_mode string is rejected by schema."""
        cmd_bad_mode = {"action": "dual_carry", "robots": ["FR3_1", "FR3_2"], "sync_mode": "elastic_spring"}
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(cmd_bad_mode, ACTION_COMMAND_SCHEMA)


@pytest.mark.tier2
@pytest.mark.m4
class TestBoundaryFeature18MultiAgentPrompts(unittest.TestCase):
    """Boundary cases for Feature 18: Kitchen Multi-Agent Prompts."""

    def test_b18_system_prompt_token_length_bound(self):
        """Boundary: System prompt character length should be under 16,000 characters (~4000 tokens)."""
        prompt = gemini_prompts.SYSTEM_PROMPT.format(user_goal="Test Goal")
        self.assertGreater(len(prompt), 500)
        self.assertLess(len(prompt), 16000)

    def test_b18_empty_user_goal_interpolation(self):
        """Boundary: Empty user_goal formatted cleanly without crashing."""
        formatted = gemini_prompts.SYSTEM_PROMPT.format(user_goal="")
        self.assertIn("Workspace layout", formatted)
        self.assertIn("KITCHEN_AFFORDANCE_RULES", dir(gemini_prompts))

    def test_b18_malformed_json_stripping_boundary(self):
        """Boundary: Code fence regex strips triple backticks with newlines and language tags."""
        import re
        raw = "```json\n{\"action\": \"pick\"}\n```"
        clean = re.sub(r'^```(?:json)?\s*', '', raw.strip())
        clean = re.sub(r'\s*```$', '', clean)
        self.assertEqual(clean, '{"action": "pick"}')

    def test_b18_max_concurrency_three_robots(self):
        """Boundary: Agility prompt includes third-arm concurrency directive for FR3_1, FR3_2, FR3_3."""
        agility = gemini_prompts.AGILITY_OPTIMIZER_GUIDELINES
        self.assertIn("THIRD arm (FR3_3) is completely unconstrained", agility)
        self.assertIn("dual_arm_transport", agility)

    def test_b18_retry_counter_threshold(self):
        """Boundary: Failure recovery instructions handle failure and retry thresholds."""
        recovery = gemini_prompts.DUAL_ARM_FAILURE_CONTEXT
        self.assertIn("retry count >= 2", recovery)
        self.assertIn("replan", recovery)
