"""Unit tests for Gemini VLA Cognitive Loop & Tool Taxonomy (Requirement R4).

Verifies:
1. Object name resolution (Dish1..3, Cup1..3, LongBar1, Block1..9) in gemini_utils.
2. Backward-compatibility of resolve_block_key alias in gemini_utils.
3. Affordance taxonomy classification (single-arm vs dual-arm).
4. Tool taxonomy schema declarations in gemini_tools (dual_arm_transport, clear_table, organize_table).
5. Cognitive prompts and guidelines in gemini_prompts (Spatial Architect & Agility Optimizer).
6. Tool dispatch payload construction and result handling in gemini_robotics_node.
"""

import sys
import os
import json
import unittest

# Ensure package modules can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
package_dir = os.path.abspath(os.path.join(current_dir, '..', 'isaac_ros2_control'))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

try:
    import gemini_utils
    import gemini_tools
    import gemini_prompts
except ImportError:
    from isaac_ros2_control import gemini_utils
    from isaac_ros2_control import gemini_tools
    from isaac_ros2_control import gemini_prompts


class TestGeminiUtilsResolution(unittest.TestCase):
    """Test object key resolution and affordance classification in gemini_utils."""

    def test_resolve_dishes(self):
        self.assertEqual(gemini_utils.resolve_object_key("Dish1"), "Dish1")
        self.assertEqual(gemini_utils.resolve_object_key("dish2"), "Dish2")
        self.assertEqual(gemini_utils.resolve_object_key("White Dish"), "Dish1")
        self.assertEqual(gemini_utils.resolve_object_key("white plate"), "Dish1")
        self.assertEqual(gemini_utils.resolve_object_key("porcelain"), "Dish1")
        self.assertEqual(gemini_utils.resolve_object_key("blue dish"), "Dish2")
        self.assertEqual(gemini_utils.resolve_object_key("cobalt"), "Dish2")
        self.assertEqual(gemini_utils.resolve_object_key("terracotta"), "Dish3")
        self.assertEqual(gemini_utils.resolve_object_key("plate3"), "Dish3")
        self.assertEqual(gemini_utils.resolve_object_key("plate"), "Dish1")

    def test_resolve_cups(self):
        self.assertEqual(gemini_utils.resolve_object_key("Cup1"), "Cup1")
        self.assertEqual(gemini_utils.resolve_object_key("cup2"), "Cup2")
        self.assertEqual(gemini_utils.resolve_object_key("amber mug"), "Cup1")
        self.assertEqual(gemini_utils.resolve_object_key("yellow cup"), "Cup1")
        self.assertEqual(gemini_utils.resolve_object_key("sage"), "Cup2")
        self.assertEqual(gemini_utils.resolve_object_key("mint"), "Cup2")
        self.assertEqual(gemini_utils.resolve_object_key("charcoal"), "Cup3")
        self.assertEqual(gemini_utils.resolve_object_key("espresso"), "Cup3")
        self.assertEqual(gemini_utils.resolve_object_key("mug"), "Cup1")

    def test_resolve_long_bar(self):
        self.assertEqual(gemini_utils.resolve_object_key("LongBar"), "LongBar1")
        self.assertEqual(gemini_utils.resolve_object_key("longbar"), "LongBar1")
        self.assertEqual(gemini_utils.resolve_object_key("long_bar"), "LongBar1")
        self.assertEqual(gemini_utils.resolve_object_key("long bar"), "LongBar1")
        self.assertEqual(gemini_utils.resolve_object_key("bar"), "LongBar1")
        self.assertEqual(gemini_utils.resolve_object_key("tray"), "LongBar1")
        self.assertEqual(gemini_utils.resolve_object_key("serving tray"), "LongBar1")

    def test_resolve_blocks(self):
        self.assertEqual(gemini_utils.resolve_object_key("Block1"), "Block1")
        self.assertEqual(gemini_utils.resolve_object_key("red"), "Block1")
        self.assertEqual(gemini_utils.resolve_object_key("Red Cube"), "Block1")
        self.assertEqual(gemini_utils.resolve_object_key("green"), "Block2")
        self.assertEqual(gemini_utils.resolve_object_key("blue block"), "Block3")
        self.assertEqual(gemini_utils.resolve_object_key("yellow cube"), "Block4")
        self.assertEqual(gemini_utils.resolve_object_key("magenta"), "Block5")
        self.assertEqual(gemini_utils.resolve_object_key("cyan"), "Block6")
        self.assertEqual(gemini_utils.resolve_object_key("orange"), "Block7")
        self.assertEqual(gemini_utils.resolve_object_key("purple"), "Block8")
        self.assertEqual(gemini_utils.resolve_object_key("lime"), "Block9")

    def test_resolve_block_key_backward_compatibility(self):
        """Ensure resolve_block_key alias works identically."""
        self.assertEqual(gemini_utils.resolve_block_key("Red Cube"), "Block1")
        self.assertEqual(gemini_utils.resolve_block_key("dish1"), "Dish1")
        self.assertEqual(gemini_utils.resolve_block_key("Cup2"), "Cup2")
        self.assertEqual(gemini_utils.resolve_block_key("LongBar"), "LongBar1")

    def test_affordance_classification(self):
        """Ensure object types are correctly classified for affordances."""
        self.assertEqual(gemini_utils.get_object_type("Dish1"), "dish")
        self.assertEqual(gemini_utils.get_object_type("White Plate"), "dish")
        self.assertEqual(gemini_utils.get_object_type("Cup2"), "cup")
        self.assertEqual(gemini_utils.get_object_type("Coffee Mug"), "cup")
        self.assertEqual(gemini_utils.get_object_type("LongBar1"), "long_bar")
        self.assertEqual(gemini_utils.get_object_type("Serving Tray"), "long_bar")
        self.assertEqual(gemini_utils.get_object_type("Block1"), "block")

        # Single-arm vs dual-arm
        self.assertTrue(gemini_utils.is_dual_arm_object("LongBar1"))
        self.assertTrue(gemini_utils.is_dual_arm_object("tray"))
        self.assertFalse(gemini_utils.is_dual_arm_object("Dish1"))
        self.assertFalse(gemini_utils.is_dual_arm_object("Cup1"))
        self.assertFalse(gemini_utils.is_dual_arm_object("Block5"))

        # Kitchenware detection
        self.assertTrue(gemini_utils.is_kitchenware("Dish1"))
        self.assertTrue(gemini_utils.is_kitchenware("Cup2"))
        self.assertTrue(gemini_utils.is_kitchenware("LongBar1"))
        self.assertFalse(gemini_utils.is_kitchenware("Block1"))


class TestGeminiToolsTaxonomy(unittest.TestCase):
    """Test GenAI Tool schema declarations in gemini_tools."""

    def test_tools_completeness(self):
        tools = gemini_tools.get_robot_tools()
        if not tools:
            self.skipTest("google-genai package not available in test environment")

        tool_declarations = tools[0].function_declarations
        func_names = [f.name for f in tool_declarations]

        # Core required tools
        self.assertIn("detect_objects", func_names)
        self.assertIn("pick", func_names)
        self.assertIn("place", func_names)
        self.assertIn("place_relative", func_names)
        self.assertIn("dual_arm_transport", func_names)
        self.assertIn("clear_table", func_names)
        self.assertIn("organize_table", func_names)
        self.assertIn("verify_tower", func_names)
        self.assertIn("go_home", func_names)

    def test_dual_arm_transport_schema(self):
        tools = gemini_tools.get_robot_tools()
        if not tools:
            self.skipTest("google-genai package not available in test environment")

        tool_map = {f.name: f for f in tools[0].function_declarations}
        dual_tool = tool_map.get("dual_arm_transport")
        self.assertIsNotNone(dual_tool)

        props = dual_tool.parameters.properties
        self.assertIn("robots", props)
        self.assertIn("object_label", props)
        self.assertIn("speed", props)
        self.assertIn("approach_height", props)

        # Check required fields
        self.assertIn("robots", dual_tool.parameters.required)
        self.assertIn("object_label", dual_tool.parameters.required)


class TestGeminiPrompts(unittest.TestCase):
    """Test cognitive prompts and guidelines in gemini_prompts."""

    def test_affordance_rules_defined(self):
        self.assertTrue(hasattr(gemini_prompts, "KITCHEN_AFFORDANCE_RULES"))
        rules = gemini_prompts.KITCHEN_AFFORDANCE_RULES
        self.assertIn("Single-Arm", rules)
        self.assertIn("Dual-Arm", rules)
        self.assertIn("Dishes", rules)
        self.assertIn("Cups", rules)
        self.assertIn("Long Bar", rules)
        self.assertIn("dual_arm_transport", rules)

    def test_spatial_architect_prompt(self):
        prompt = gemini_prompts.get_spatial_architect_prompt(
            architect_model="gemini-2.5-flash",
            goal_text="Set the dining table with plates and cups and transfer long bar",
            draft_plan="FR3_1 picks dish, FR3_2 picks cup"
        )
        self.assertIn("Spatial Architect", prompt)
        self.assertIn("Dual-Arm Grasp Waypoints", prompt)
        self.assertIn("Kitchen Dining Table Layout", prompt)
        self.assertIn("relation=", prompt)

    def test_agility_optimizer_prompt(self):
        prompt = gemini_prompts.get_agility_optimizer_prompt(
            optimizer_model="gemini-2.5-flash",
            geometric_plan="Grasp points: (Xc-0.22, Yc) and (Xc+0.22, Yc)"
        )
        self.assertIn("Performance Optimizer", prompt)
        self.assertIn("speed='fast'", prompt)
        self.assertIn("Dual-Arm Concurrency", prompt)
        self.assertIn("THIRD robot", prompt)

    def test_system_prompt_kitchen_awareness(self):
        sys_prompt = gemini_prompts.SYSTEM_PROMPT
        self.assertIn("KITCHEN_AFFORDANCE_RULES", str(gemini_prompts))
        self.assertIn("dual_arm_transport", sys_prompt)
        self.assertIn("clear_table", sys_prompt)
        self.assertIn("organize_table", sys_prompt)


class TestGeminiRoboticsNodeDispatch(unittest.TestCase):
    """Test tool execution dispatch logic in gemini_robotics_node."""

    def setUp(self):
        # Create a mock action publisher and mock node state
        class MockPublisher:
            def __init__(self):
                self.messages = []
            def publish(self, msg):
                self.messages.append(msg.data)

        class MockLogger:
            def info(self, *a, **kw): pass
            def warn(self, *a, **kw): pass
            def error(self, *a, **kw): pass

        self.publisher = MockPublisher()
        self.logger = MockLogger()

    def test_dual_arm_transport_payload_structure(self):
        """Verify the JSON payload emitted on /gemini/action for dual_arm_transport."""
        from isaac_ros2_control import gemini_robotics_node

        # Instantiate a lightweight Mock wrapper around GeminiRoboticsNode methods
        class MockNode:
            action_pub = self.publisher
            action_results = {"DUAL_FR3_1_FR3_2": {"success": True, "message": "Collaborative transport complete."}}
            cancel_current_task = False
            get_logger = lambda s: self.logger

            _fn_dual_arm_transport = gemini_robotics_node.GeminiRoboticsNode._fn_dual_arm_transport
            _wait_for_collaborative_action_complete = gemini_robotics_node.GeminiRoboticsNode._wait_for_collaborative_action_complete

        mock = MockNode()
        res = mock._fn_dual_arm_transport(
            robots=["FR3_1", "FR3_2"],
            object_label="LongBar",
            target_x=0.0,
            target_y=0.0,
            target_z=0.05,
            speed="fast",
            approach_height=0.12
        )

        self.assertEqual(len(self.publisher.messages), 1)
        payload = json.loads(self.publisher.messages[0])
        self.assertEqual(payload["action"], "dual_carry")
        self.assertEqual(payload["robots"], ["FR3_1", "FR3_2"])
        self.assertEqual(payload["object"], "LongBar1")
        self.assertEqual(payload["destination"], [0.0, 0.0, 0.05])
        self.assertEqual(payload["sync_mode"], "rigid_body")
        self.assertEqual(payload["speed"], "fast")
        self.assertEqual(payload["approach_height"], 0.12)
        self.assertTrue(res.get("success"))

    def test_clear_and_organize_table_payloads(self):
        """Verify clear_table and organize_table payloads."""
        from isaac_ros2_control import gemini_robotics_node

        class MockNode:
            action_pub = self.publisher
            action_results = {
                "FR3_1": {"success": True, "message": "Done"},
                "FR3_2": {"success": True, "message": "Done"}
            }
            cancel_current_task = False
            get_logger = lambda s: self.logger

            _fn_clear_table = gemini_robotics_node.GeminiRoboticsNode._fn_clear_table
            _fn_organize_table = gemini_robotics_node.GeminiRoboticsNode._fn_organize_table
            _wait_for_action_complete = gemini_robotics_node.GeminiRoboticsNode._wait_for_action_complete

        mock = MockNode()
        mock._fn_clear_table(robot="FR3_1", object_label="Dish1", zone="dish_rack")
        clear_payload = json.loads(self.publisher.messages[0])
        self.assertEqual(clear_payload["action"], "clear_table")
        self.assertEqual(clear_payload["robot"], "FR3_1")
        self.assertEqual(clear_payload["target"], "Dish1")
        self.assertEqual(clear_payload["zone"], "dish_rack")

        mock._fn_organize_table(robot="FR3_2", object_label="Cup2", layout="dining")
        org_payload = json.loads(self.publisher.messages[1])
        self.assertEqual(org_payload["action"], "organize_table")
        self.assertEqual(org_payload["robot"], "FR3_2")
        self.assertEqual(org_payload["target"], "Cup2")
        self.assertEqual(org_payload["layout"], "dining")


if __name__ == '__main__':
    unittest.main()
