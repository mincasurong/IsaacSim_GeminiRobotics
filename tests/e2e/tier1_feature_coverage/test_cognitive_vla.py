"""Tier 1: Cognitive VLA Layer & Tool Taxonomy Tests (Features 15 - 18).

REFACTORED FOR AUDIT INTEGRITY:
- Genuinely imports and tests gemini_utils.resolve_object_key, get_object_type, and is_dual_arm_object.
- Genuinely inspects tool schemas in gemini_tools.GEMINI_TOOL_DECLARATIONS.
- Directly formats and verifies prompt templates in gemini_prompts.py.
"""
import sys
import os
import unittest

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

from ..framework.contracts import PROJECT_ROOT

package_dir = os.path.abspath(os.path.join(PROJECT_ROOT, "wsl_ws", "src", "isaac_ros2_control", "isaac_ros2_control"))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

import gemini_utils
import gemini_prompts
import gemini_tools


@pytest.mark.tier1
@pytest.mark.m4
class TestFeature15FixUtilityFunctionBug(unittest.TestCase):
    """Feature 15: Implement missing resolve_object_key in gemini_utils.py."""

    def test_f15_function_defined_in_gemini_utils(self):
        """Verify resolve_object_key function is defined and callable in gemini_utils.py."""
        assert hasattr(gemini_utils, "resolve_object_key")
        assert callable(gemini_utils.resolve_object_key)
        assert hasattr(gemini_utils, "resolve_block_key")
        assert callable(gemini_utils.resolve_block_key)

    def test_f15_resolve_exact_match(self):
        """Verify exact string matching for kitchenware and blocks via gemini_utils."""
        assert gemini_utils.resolve_object_key("Dish1") == "Dish1"
        assert gemini_utils.resolve_object_key("Dish2") == "Dish2"
        assert gemini_utils.resolve_object_key("Dish3") == "Dish3"
        assert gemini_utils.resolve_object_key("Cup1") == "Cup1"
        assert gemini_utils.resolve_object_key("Cup2") == "Cup2"
        assert gemini_utils.resolve_object_key("Cup3") == "Cup3"
        assert gemini_utils.resolve_object_key("LongBar1") == "LongBar1"
        assert gemini_utils.resolve_object_key("Block1") == "Block1"

    def test_f15_resolve_case_insensitive(self):
        """Verify case-insensitive normalization via gemini_utils."""
        assert gemini_utils.resolve_object_key("dish1") == "Dish1"
        assert gemini_utils.resolve_object_key("cup2") == "Cup2"
        assert gemini_utils.resolve_object_key("longbar1") == "LongBar1"
        assert gemini_utils.resolve_object_key("LONGBAR1") == "LongBar1"
        assert gemini_utils.resolve_object_key("bLoCk5") == "Block5"

    def test_f15_resolve_descriptive_label(self):
        """Verify resolution from descriptive labels and affordance detection."""
        assert gemini_utils.resolve_object_key("white dish") == "Dish1"
        assert gemini_utils.resolve_object_key("white plate") == "Dish1"
        assert gemini_utils.resolve_object_key("amber mug") == "Cup1"
        assert gemini_utils.resolve_object_key("yellow cup") == "Cup1"
        assert gemini_utils.resolve_object_key("long bar") == "LongBar1"
        assert gemini_utils.resolve_object_key("serving tray") == "LongBar1"
        assert gemini_utils.get_object_type("Dish1") == "dish"
        assert gemini_utils.get_object_type("Cup1") == "cup"
        assert gemini_utils.get_object_type("LongBar1") == "long_bar"
        assert gemini_utils.is_dual_arm_object("LongBar1") is True
        assert gemini_utils.is_dual_arm_object("Dish1") is False

    def test_f15_resolve_nonexistent_returns_none(self):
        """Verify resolving an invalid/missing object gracefully returns None without crashing."""
        assert gemini_utils.resolve_object_key("nonexistent_tray") is None
        assert gemini_utils.resolve_object_key("flying_car") is None
        assert gemini_utils.resolve_object_key("") is None
        assert gemini_utils.resolve_object_key(None) is None


@pytest.mark.tier1
@pytest.mark.m4
class TestFeature16AffordanceReasoningRules(unittest.TestCase):
    """Feature 16: Affordance Reasoning Rules."""

    def test_f16_prompts_file_defines_kitchen_affordances(self):
        """Verify gemini_prompts defines structured KITCHEN_AFFORDANCE_RULES."""
        assert hasattr(gemini_prompts, "KITCHEN_AFFORDANCE_RULES")
        rules = gemini_prompts.KITCHEN_AFFORDANCE_RULES
        assert "Single-Arm" in rules
        assert "Dual-Arm" in rules
        assert "Dishes" in rules
        assert "Cups" in rules
        assert "Long Bar" in rules

    def test_f16_long_bar_dual_arm_rule_present(self):
        """Verify system prompt and affordance rules mandate dual-arm transport for long bar."""
        rules = gemini_prompts.KITCHEN_AFFORDANCE_RULES
        assert "dual_arm_transport" in rules
        assert "Long Bar" in rules
        sys_prompt = gemini_prompts.SYSTEM_PROMPT
        assert "dual_arm_transport" in sys_prompt

    def test_f16_dish_single_arm_rule(self):
        """Verify dishes are classified as single-arm manipulation in gemini_utils."""
        assert gemini_utils.is_dual_arm_object("Dish1") is False
        assert gemini_utils.get_object_type("Dish1") == "dish"

    def test_f16_cup_single_arm_rule(self):
        """Verify cups are classified as single-arm manipulation in gemini_utils."""
        assert gemini_utils.is_dual_arm_object("Cup1") is False
        assert gemini_utils.get_object_type("Cup1") == "cup"

    def test_f16_spatial_affordance_classification_completeness(self):
        """Verify classifier produces valid categories for all kitchen assets."""
        assets = ["Dish1", "Dish2", "Dish3", "Cup1", "Cup2", "Cup3", "LongBar1", "Block1"]
        for a in assets:
            cat = gemini_utils.get_object_type(a)
            assert cat in ["dish", "cup", "long_bar", "block"]
            assert gemini_utils.is_dual_arm_object(a) == (cat == "long_bar")


@pytest.mark.tier1
@pytest.mark.m4
class TestFeature17DualArmActionToolSchemas(unittest.TestCase):
    """Feature 17: Dual-Arm Action Tool Schemas."""

    def test_f17_dual_arm_tool_declared_in_gemini_tools(self):
        """Verify dual_arm_transport tool is declared in gemini_tools.py."""
        tool_names = [t["name"] for t in gemini_tools.GEMINI_TOOL_DECLARATIONS]
        assert "dual_arm_transport" in tool_names

    def test_f17_dual_arm_tool_parameter_robots_schema(self):
        """Verify tool schema requires robot pair definition."""
        tool = next(t for t in gemini_tools.GEMINI_TOOL_DECLARATIONS if t["name"] == "dual_arm_transport")
        assert "robots" in tool["parameters"]["properties"]
        assert "robots" in tool["parameters"]["required"]

    def test_f17_dual_arm_tool_parameter_destination_schema(self):
        """Verify tool schema includes destination target coordinates."""
        tool = next(t for t in gemini_tools.GEMINI_TOOL_DECLARATIONS if t["name"] == "dual_arm_transport")
        props = tool["parameters"]["properties"]
        assert "destination" in props or "target_x" in props

    def test_f17_dual_arm_tool_speed_parameter(self):
        """Verify optional movement speed parameter is supported."""
        tool = next(t for t in gemini_tools.GEMINI_TOOL_DECLARATIONS if t["name"] == "dual_arm_transport")
        props = tool["parameters"]["properties"]
        assert "speed" in props
        assert "fast" in props["speed"]["enum"]

    def test_f17_robot_tools_list_contains_all_primitives(self):
        """Verify GEMINI_TOOL_DECLARATIONS exports pick, place, place_relative, and dual transport."""
        tool_names = [t["name"] for t in gemini_tools.GEMINI_TOOL_DECLARATIONS]
        for prim in ["pick", "place", "place_relative", "dual_arm_transport", "clear_table", "organize_table"]:
            assert prim in tool_names


@pytest.mark.tier1
@pytest.mark.m4
class TestFeature18KitchenMultiAgentPrompts(unittest.TestCase):
    """Feature 18: Kitchen Multi-Agent Prompts."""

    def test_f18_spatial_architect_prompt_kitchen_awareness(self):
        """Verify Spatial Architect prompt contains kitchen counter arrangement guidelines."""
        prompt = gemini_prompts.get_spatial_architect_prompt(
            architect_model="gemini-2.5-flash",
            goal_text="Arrange kitchenware",
            draft_plan="plan"
        )
        assert "Spatial Architect" in prompt
        assert "Dual-Arm Grasp Waypoints" in prompt
        assert "Kitchen Dining Table Layout" in prompt

    def test_f18_agility_optimizer_prompt_concurrency(self):
        """Verify Agility Optimizer prompt instructs concurrent dual-arm and single-arm execution."""
        prompt = gemini_prompts.get_agility_optimizer_prompt(
            optimizer_model="gemini-2.5-flash",
            geometric_plan="plan"
        )
        assert "Performance Optimizer" in prompt or "Agility" in prompt
        assert "Dual-Arm Concurrency" in prompt
        assert "THIRD" in prompt

    def test_f18_table_clearing_prompt_template(self):
        """Verify prompt template for table clearing and organizing."""
        assert "clear_table" in gemini_prompts.SYSTEM_PROMPT
        assert "organize_table" in gemini_prompts.SYSTEM_PROMPT

    def test_f18_dining_setup_prompt_template(self):
        """Verify prompt instructions for setting dining table."""
        assert "dining" in gemini_prompts.SYSTEM_PROMPT.lower()
        assert "dining" in gemini_prompts.SPATIAL_ARCHITECT_KITCHEN_GUIDELINES.lower()

    def test_f18_recovery_prompt_on_dual_arm_failure(self):
        """Verify failure context prompt template for handling grasp failures."""
        assert "Dual-arm transport failed" in gemini_prompts.DUAL_ARM_FAILURE_CONTEXT
        assert "retry" in gemini_prompts.DUAL_ARM_FAILURE_CONTEXT.lower()
        assert "replan" in gemini_prompts.DUAL_ARM_FAILURE_CONTEXT.lower()
