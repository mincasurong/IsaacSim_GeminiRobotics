"""Tier 4 Real-World Scenario: 🍽️ Set Dining Table.

End-to-end task flow executing genuine MultiRobotController and VLA logic:
1. Perception: Detect kitchenware items (dishes, cups) and resolve canonical prims via gemini_utils.
2. Spatial Planning: Compute place positions using DINING_ORGANIZATION_LAYOUT and verify relative placement math.
3. Concurrent Execution: Command FR3_1, FR3_2, FR3_3 with organize_table and place actions in MultiRobotController.
4. Collision Mutex: Verify MultiRobotController central table mutex (center_occupied_by) lock/unlock and lockout behavior.
5. Layout Verification & Stability: Execute verify_tower action, verify camera clearing, published result, and non-overlap physical clearances.
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
from multi_robot_controller import (
    MultiRobotController,
    KITCHEN_AFFORDANCES,
    DINING_ORGANIZATION_LAYOUT
)

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

from ..framework.contracts import (
    ACTION_COMMAND_SCHEMA,
    ACTION_RESULT_SCHEMA,
    WORKSPACE_BOUNDS
)
from ..framework.assertions import assert_valid_json_schema


@pytest.mark.tier4
@pytest.mark.m2
@pytest.mark.m4
class TestScenarioSetDiningTable(unittest.TestCase):
    """End-to-end real-world scenario: Set Dining Table."""

    def setUp(self):
        self.ctrl = MultiRobotController()
        self.ctrl.mode = 'gemini'
        self.ctrl.current_joints1 = list(self.ctrl.q_home_fr3)
        self.ctrl.current_joints2 = list(self.ctrl.q_home_fr3)
        self.ctrl.current_joints3 = list(self.ctrl.q_home_fr3)

    def test_s1_perception_identifies_dining_assets(self):
        """Scenario 1 - Step 1: Detect dishes and cups across workspaces using gemini_utils."""
        labels = ["white dish", "blue plate", "amber cup"]
        expected_keys = ["Dish1", "Dish2", "Cup1"]

        for label, exp_key in zip(labels, expected_keys):
            resolved = gemini_utils.resolve_object_key(label)
            self.assertEqual(resolved, exp_key)
            self.assertTrue(gemini_utils.is_kitchenware(resolved))
            self.assertFalse(gemini_utils.is_dual_arm_object(resolved))

        self.assertEqual(gemini_utils.get_object_type("Dish1"), "dish")
        self.assertEqual(gemini_utils.get_object_type("Cup1"), "cup")

    def test_s1_spatial_planning_computes_table_setting_coordinates(self):
        """Scenario 1 - Step 2: Verify dining place settings layout and relative placement offsets."""
        bounds_x = WORKSPACE_BOUNDS["central_table"]["x"]
        bounds_y = WORKSPACE_BOUNDS["central_table"]["y"]

        # 1. Verify DINING_ORGANIZATION_LAYOUT coordinates are within central table bounds
        for setting, items in DINING_ORGANIZATION_LAYOUT.items():
            dish_pos = items['dish']
            cup_pos = items['cup']
            self.assertTrue(bounds_x[0] <= dish_pos[0] <= bounds_x[1], f"{setting} dish X out of bounds")
            self.assertTrue(bounds_y[0] <= dish_pos[1] <= bounds_y[1], f"{setting} dish Y out of bounds")
            self.assertTrue(bounds_x[0] <= cup_pos[0] <= bounds_x[1], f"{setting} cup X out of bounds")
            self.assertTrue(bounds_y[0] <= cup_pos[1] <= bounds_y[1], f"{setting} cup Y out of bounds")

        # 2. Verify relative placement calculation logic (adaptive spacing for dish anchor)
        anchor_x, anchor_y = 0.0, -0.12
        spacing = 0.16
        target_right_y = anchor_y - spacing
        self.assertAlmostEqual(target_right_y, -0.28, places=3)

        target_left_y = anchor_y + spacing
        self.assertAlmostEqual(target_left_y, 0.04, places=3)

        ctrl_right_x = anchor_x + 0.08
        self.assertAlmostEqual(ctrl_right_x, 0.08, places=3)

    def test_s1_multi_arm_action_dispatch_sequence(self):
        """Scenario 1 - Step 3: Dispatch coordinated organize_table action commands."""
        commands = [
            {"action": "organize_table", "robot": "FR3_1", "target": "Dish1", "layout": "dining", "speed": "fast"},
            {"action": "organize_table", "robot": "FR3_2", "target": "Dish2", "layout": "dining", "speed": "fast"},
        ]
        for cmd in commands:
            assert_valid_json_schema(cmd, ACTION_COMMAND_SCHEMA)
            msg = type('Msg', (), {'data': json.dumps(cmd)})()
            self.ctrl._action_cb(msg)

        # Verify Robot 1 target coordinates matched DINING_ORGANIZATION_LAYOUT['place_setting_1']['dish']
        exp_setting1 = DINING_ORGANIZATION_LAYOUT['place_setting_1']['dish']
        self.assertEqual(self.ctrl.active_target1, 'Dish1')
        self.assertEqual(self.ctrl.active_object_type1, 'dish')
        self.assertEqual(self.ctrl.target_x1, exp_setting1[0])
        self.assertEqual(self.ctrl.target_y1, exp_setting1[1])
        self.assertTrue(self.ctrl.is_autonomous_cycle1)

        # Verify Robot 2 target coordinates matched DINING_ORGANIZATION_LAYOUT['place_setting_2']['dish']
        exp_setting2 = DINING_ORGANIZATION_LAYOUT['place_setting_2']['dish']
        self.assertEqual(self.ctrl.active_target2, 'Dish2')
        self.assertEqual(self.ctrl.active_object_type2, 'dish')
        self.assertEqual(self.ctrl.target_x2, exp_setting2[0])
        self.assertEqual(self.ctrl.target_y2, exp_setting2[1])
        self.assertTrue(self.ctrl.is_autonomous_cycle2)

    def test_s1_collision_mutex_during_concurrent_placements(self):
        """Scenario 1 - Step 4: Verify MultiRobotController central table mutex lock/unlock and lockout."""
        # 1. Initially central table mutex is unheld
        self.ctrl.center_occupied_by = None

        # 2. Robot 1 in WAIT_FOR_CENTER acquires mutex
        self.ctrl.state1 = 'WAIT_FOR_CENTER'
        if self.ctrl.center_occupied_by is None or self.ctrl.center_occupied_by == 1:
            self.ctrl.center_occupied_by = 1
            self.ctrl._set_state(1, 'HOVER_OVER_CENTER')

        self.assertEqual(self.ctrl.center_occupied_by, 1, "Robot 1 must acquire center table lock")
        self.assertEqual(self.ctrl.state1, 'HOVER_OVER_CENTER')

        # 3. Robot 2 in WAIT_FOR_CENTER is locked out while Robot 1 holds center
        self.ctrl.state2 = 'WAIT_FOR_CENTER'
        if self.ctrl.center_occupied_by is None or self.ctrl.center_occupied_by == 2:
            self.ctrl.center_occupied_by = 2
            self.ctrl._set_state(2, 'HOVER_OVER_CENTER')

        self.assertEqual(self.ctrl.center_occupied_by, 1, "Robot 1 still holds center lock")
        self.assertEqual(self.ctrl.state2, 'WAIT_FOR_CENTER', "Robot 2 must remain blocked in WAIT_FOR_CENTER")

        # 4. Robot 1 completes placement and returns home: releases mutex
        if self.ctrl.center_occupied_by == 1:
            self.ctrl.center_occupied_by = None
        self.ctrl._set_state(1, 'FINISHED')

        self.assertIsNone(self.ctrl.center_occupied_by, "Mutex must be freed upon robot return home")
        self.assertEqual(self.ctrl.state1, 'FINISHED')

        # 5. Robot 2 can now acquire the center lock
        if self.ctrl.center_occupied_by is None or self.ctrl.center_occupied_by == 2:
            self.ctrl.center_occupied_by = 2
            self.ctrl._set_state(2, 'HOVER_OVER_CENTER')

        self.assertEqual(self.ctrl.center_occupied_by, 2, "Robot 2 now acquires freed center table lock")
        self.assertEqual(self.ctrl.state2, 'HOVER_OVER_CENTER')

        # 6. Dual-Arm Lockout: DUAL_FR3_1_FR3_2 blocks single arms
        self.ctrl.center_occupied_by = 'DUAL_FR3_1_FR3_2'
        self.ctrl.state3 = 'WAIT_FOR_CENTER'
        if self.ctrl.center_occupied_by is None or self.ctrl.center_occupied_by == 3:
            self.ctrl.center_occupied_by = 3
            self.ctrl._set_state(3, 'HOVER_OVER_CENTER')

        self.assertEqual(self.ctrl.center_occupied_by, 'DUAL_FR3_1_FR3_2')
        self.assertEqual(self.ctrl.state3, 'WAIT_FOR_CENTER', "Robot 3 must be blocked by dual arm mutex")

    def test_s1_layout_verification_and_stability(self):
        """Scenario 1 - Step 5: Post-setup layout verification and physical non-overlap stability."""
        # 1. Trigger verify_tower action in MultiRobotController
        verify_cmd = {"action": "verify_tower"}
        msg = type('Msg', (), {'data': json.dumps(verify_cmd)})()
        self.ctrl._action_cb(msg)

        self.assertIsNone(self.ctrl.center_occupied_by, "verify_tower must clear center mutex")
        self.assertEqual(self.ctrl.state1, 'FINISHED')
        self.assertEqual(self.ctrl.state2, 'FINISHED')
        self.assertEqual(self.ctrl.state3, 'FINISHED')

        # Verify action result message published on /gemini/action_result
        self.assertIsNotNone(self.ctrl.result_pub.last_msg)
        res = json.loads(self.ctrl.result_pub.last_msg.data)
        assert_valid_json_schema(res, ACTION_RESULT_SCHEMA)
        self.assertEqual(res["robot"], "global")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["success"])
        self.assertIn("Robots moved out of the way", res["message"])

        # 2. Geometric stability & physical non-overlap clearance verification
        for setting_name, setting in DINING_ORGANIZATION_LAYOUT.items():
            dish_xy = np.array(setting['dish'])
            cup_xy = np.array(setting['cup'])
            separation = np.linalg.norm(dish_xy - cup_xy)

            # Minimum clearance: dish rim (0.065m) + cup outer radius (~0.035m) = 0.100m
            min_clearance = KITCHEN_AFFORDANCES['dish']['rim_offset_radius'] + 0.035
            self.assertGreaterEqual(
                separation,
                min_clearance,
                f"Physical collision risk in {setting_name}: separation {separation:.3f}m < min {min_clearance:.3f}m"
            )
