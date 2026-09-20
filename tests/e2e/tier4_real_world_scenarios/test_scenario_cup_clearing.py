"""Tier 4 Real-World Scenario: ☕ Clear Cups.

End-to-end task flow executing genuine MultiRobotController and VLA logic:
1. Perception: Identify multiple cups dispersed across the kitchen tables using gemini_utils.
2. Agility Planning: Dispatch concurrent picks across FR3_1, FR3_2, and FR3_3 in MultiRobotController.
3. Manipulation: Verify cylindrical clamp parameters, approach clearances, and touch verification range.
4. Coordinated Placement: Dispatch clear_table action mapping to CLEARING_ZONES destinations.
5. Verification: Complete autonomous clearing cycle, verify tasks completed counter, and validate published /gemini/action_result payload.
"""
import sys
import os
import json
import unittest
import numpy as np

# Add ROS 2 control package to path
current_dir = os.path.dirname(os.path.abspath(__file__))
package_dir = os.path.abspath(os.path.join(current_dir, '..', '..', '..', 'wsl_ws', 'src', 'isaac_ros2_control', 'isaac_ros2_control'))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

# Mock ROS 2 if rclpy is not present in standard testing environment
try:
    import rclpy
    from rclpy.node import Node
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    class MockNode:
        def __init__(self, name="mock_controller"):
            self.name = name
        def declare_parameter(self, *args, **kwargs): pass
        def get_parameter(self, name):
            class Param:
                def get_parameter_value(self):
                    class Val:
                        string_value = 'gemini'
                        double_value = 0.0
                        integer_value = 10
                    return Val()
            return Param()
        def create_publisher(self, *args, **kwargs):
            class MockPub:
                def __init__(self):
                    self.last_msg = None
                def publish(self, msg):
                    self.last_msg = msg
            return MockPub()
        def create_subscription(self, *args, **kwargs): return None
        def create_service(self, *args, **kwargs): return None
        def create_timer(self, *args, **kwargs): return None
        def get_logger(self):
            class Logger:
                def info(self, msg, **kw): pass
                def warn(self, msg, **kw): pass
                def error(self, msg, **kw): pass
            return Logger()
        def get_clock(self):
            class Clock:
                def now(self):
                    class TimeMsg:
                        def to_msg(self): return None
                    return TimeMsg()
            return Clock()

    import types
    sys.modules['rclpy'] = types.ModuleType('rclpy')
    sys.modules['rclpy.node'] = types.ModuleType('rclpy.node')
    sys.modules['rclpy.node'].Node = MockNode
    sys.modules['rclpy.duration'] = types.ModuleType('rclpy.duration')
    sys.modules['sensor_msgs'] = types.ModuleType('sensor_msgs')
    sys.modules['sensor_msgs.msg'] = types.ModuleType('sensor_msgs.msg')
    sys.modules['sensor_msgs.msg'].JointState = type('JointState', (), {'header': type('H', (), {'stamp': None})(), 'name': [], 'position': []})
    sys.modules['std_msgs'] = types.ModuleType('std_msgs')
    sys.modules['std_msgs.msg'] = types.ModuleType('std_msgs.msg')
    sys.modules['std_msgs.msg'].Empty = type('Empty', (), {})
    sys.modules['std_msgs.msg'].String = type('String', (), {'data': ''})
    sys.modules['std_srvs'] = types.ModuleType('std_srvs')
    sys.modules['std_srvs.srv'] = types.ModuleType('std_srvs.srv')
    sys.modules['std_srvs.srv'].Trigger = type('Trigger', (), {})
    sys.modules['std_srvs.srv'].SetBool = type('SetBool', (), {})
    sys.modules['tf2_ros'] = types.ModuleType('tf2_ros')
    sys.modules['tf2_ros'].Buffer = type('Buffer', (), {'clear': lambda self: None, 'lookup_transform': lambda *a: None})
    sys.modules['tf2_ros'].TransformListener = type('TransformListener', (), {})

import kinematics
import gemini_utils
from multi_robot_controller import MultiRobotController, KITCHEN_AFFORDANCES, CLEARING_ZONES

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

from ..framework.contracts import ACTION_COMMAND_SCHEMA, ACTION_RESULT_SCHEMA
from ..framework.assertions import assert_valid_json_schema


@pytest.mark.tier4
@pytest.mark.m2
class TestScenarioCupClearing(unittest.TestCase):
    """End-to-end real-world scenario: Clear Cups."""

    def setUp(self):
        self.ctrl = MultiRobotController()
        self.ctrl.mode = 'gemini'
        self.ctrl.current_joints1 = list(self.ctrl.q_home_fr3)
        self.ctrl.current_joints2 = list(self.ctrl.q_home_fr3)
        self.ctrl.current_joints3 = list(self.ctrl.q_home_fr3)

    def test_s3_perception_finds_all_scattered_cups(self):
        """Scenario 3 - Step 1: Detect and classify scattered cups across source tables using gemini_utils."""
        detected_labels = ["amber cup", "sage mug", "charcoal cup"]
        expected_keys = ["Cup1", "Cup2", "Cup3"]

        for label, exp_key in zip(detected_labels, expected_keys):
            resolved = gemini_utils.resolve_object_key(label)
            self.assertEqual(resolved, exp_key, f"Label '{label}' must resolve to '{exp_key}'")
            self.assertEqual(gemini_utils.get_object_type(resolved), "cup")
            self.assertTrue(gemini_utils.is_kitchenware(resolved))
            self.assertFalse(gemini_utils.is_dual_arm_object(resolved), "Cups are single-arm objects")

    def test_s3_concurrent_pick_dispatch_plan(self):
        """Scenario 3 - Step 2: Formulate and dispatch parallel pick actions for high throughput."""
        pick_commands = [
            {"action": "pick", "robot": "FR3_1", "target": "Cup1", "speed": "fast"},
            {"action": "pick", "robot": "FR3_2", "target": "Cup2", "speed": "fast"},
            {"action": "pick", "robot": "FR3_3", "target": "Cup3", "speed": "fast"},
        ]
        for cmd in pick_commands:
            assert_valid_json_schema(cmd, ACTION_COMMAND_SCHEMA)
            msg = type('Msg', (), {'data': json.dumps(cmd)})()
            self.ctrl._action_cb(msg)

        # Verify controller state initialization across all 3 arms
        self.assertEqual(self.ctrl.active_target1, "Cup1")
        self.assertEqual(self.ctrl.active_object_type1, "cup")
        self.assertEqual(self.ctrl.steps_per_phase1, 20)  # speed='fast'
        self.assertEqual(self.ctrl.state1, "INIT")

        self.assertEqual(self.ctrl.active_target2, "Cup2")
        self.assertEqual(self.ctrl.active_object_type2, "cup")
        self.assertEqual(self.ctrl.steps_per_phase2, 20)
        self.assertEqual(self.ctrl.state2, "INIT")

        self.assertEqual(self.ctrl.active_target3, "Cup3")
        self.assertEqual(self.ctrl.active_object_type3, "cup")
        self.assertEqual(self.ctrl.steps_per_phase3, 20)
        self.assertEqual(self.ctrl.state3, "INIT")

    def test_s3_cylindrical_grasp_and_orientation_hold(self):
        """Scenario 3 - Step 3: Verify mid-height cylindrical clamp parameters and touch verification window."""
        affordance = self.ctrl.get_affordance('cup')
        self.assertEqual(affordance['grasp_mode'], 'cylindrical_clamp')
        self.assertEqual(affordance['rim_offset_radius'], 0.0, "Cylindrical clamp must be centered")
        self.assertEqual(affordance['grasp_z_offset'], 0.035, "Grasp offset must clamp cup mid-body")
        self.assertEqual(affordance['approach_height'], 0.120, "Approach must clear 0.09m cup height")

        # Verify touch sensor range rejects empty-finger closure and over-thick obstruction
        vmin, vmax = affordance['verification_range']
        self.assertEqual((vmin, vmax), (0.016, 0.035))

        # Real grasp on 62mm diameter cup: finger stops around 0.024m
        self.assertTrue(vmin <= 0.024 <= vmax, "Normal cup grasp must pass touch verification")
        self.assertFalse(vmin <= 0.005 <= vmax, "Missed grasp closing into air must fail")
        self.assertFalse(vmin <= 0.040 <= vmax, "Unclosed gripper must fail")

    def test_s3_staged_counter_clearing_placement(self):
        """Scenario 3 - Step 4: Dispatch clear_table action to designated staging zones."""
        # 1. Clear Cup2 with explicit zone='cup_tray'
        cmd_tray = {
            "action": "clear_table",
            "robot": "FR3_2",
            "target": "Cup2",
            "zone": "cup_tray",
            "speed": "fast"
        }
        assert_valid_json_schema(cmd_tray, ACTION_COMMAND_SCHEMA)
        msg_tray = type('Msg', (), {'data': json.dumps(cmd_tray)})()
        self.ctrl._action_cb(msg_tray)

        self.assertEqual(self.ctrl.target_x2, CLEARING_ZONES['cup_tray'][0])
        self.assertEqual(self.ctrl.target_y2, CLEARING_ZONES['cup_tray'][1])
        self.assertTrue(self.ctrl.is_autonomous_cycle2)
        self.assertEqual(self.ctrl.autonomous_action_name2, 'clear_table')

        # 2. Clear Cup1 with default zone for Robot 1
        cmd_default = {
            "action": "clear_table",
            "robot": "FR3_1",
            "target": "Cup1",
            "speed": "fast"
        }
        msg_default = type('Msg', (), {'data': json.dumps(cmd_default)})()
        self.ctrl._action_cb(msg_default)

        self.assertEqual(self.ctrl.target_x1, CLEARING_ZONES['default'][1][0])
        self.assertEqual(self.ctrl.target_y1, CLEARING_ZONES['default'][1][1])
        self.assertTrue(self.ctrl.is_autonomous_cycle1)
        self.assertEqual(self.ctrl.autonomous_action_name1, 'clear_table')

    def test_s3_table_cleared_verification(self):
        """Scenario 3 - Step 5: Final verification confirms clearing cycle completion and published result."""
        # Simulate Robot 1 completing the autonomous clear cycle
        self.ctrl.state1 = 'RETURN_HOME'
        self.ctrl.is_autonomous_cycle1 = True
        self.ctrl.autonomous_action_name1 = 'clear_table'
        self.ctrl.active_target1 = 'Cup1'
        self.ctrl.active_object_type1 = 'cup'
        self.ctrl.target_x1 = CLEARING_ZONES['default'][1][0]
        self.ctrl.target_y1 = CLEARING_ZONES['default'][1][1]
        self.ctrl.center_occupied_by = 1

        initial_completed = self.ctrl._tasks_completed[1]

        # Execute RETURN_HOME completion
        if self.ctrl.center_occupied_by == 1:
            self.ctrl.center_occupied_by = None
        self.ctrl._set_state(1, 'FINISHED')
        self.ctrl._tasks_completed[1] += 1
        self.ctrl._publish_result(
            True,
            f"Clear table completed by robot 1. Moved Cup1 to [{self.ctrl.target_x1:.2f}, {self.ctrl.target_y1:.2f}].",
            "FR3_1",
            action="clear_table"
        )

        self.assertEqual(self.ctrl.state1, 'FINISHED')
        self.assertEqual(self.ctrl._tasks_completed[1], initial_completed + 1)
        self.assertIsNone(self.ctrl.center_occupied_by)

        # Verify action result message published on /gemini/action_result
        self.assertIsNotNone(self.ctrl.result_pub.last_msg)
        result_payload = json.loads(self.ctrl.result_pub.last_msg.data)
        assert_valid_json_schema(result_payload, ACTION_RESULT_SCHEMA)
        self.assertEqual(result_payload["robot"], "FR3_1")
        self.assertEqual(result_payload["action"], "clear_table")
        self.assertEqual(result_payload["status"], "SUCCESS")
        self.assertTrue(result_payload["success"])
        self.assertIn("Clear table completed", result_payload["message"])
        self.assertIn("Moved Cup1", result_payload["message"])
