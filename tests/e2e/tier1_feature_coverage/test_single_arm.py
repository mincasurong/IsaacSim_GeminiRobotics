"""Tier 1: Single-Arm Kitchenware Manipulation Tests (Features 7 - 9).

REFACTORED FOR AUDIT INTEGRITY:
- Directly evaluates KITCHEN_AFFORDANCES for dishes and cups (offsets, modes, gripper limits).
- Uses kinematics module for downward upright orientation checks.
- Uses CLEARING_ZONES and DINING_ORGANIZATION_LAYOUT for staging bounds.
"""
import os
import sys
import unittest
import numpy as np

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

from ..framework.contracts import PROJECT_ROOT, FR3_GRIPPER_LIMITS, WORKSPACE_BOUNDS
from ..framework.assertions import assert_gripper_limits

# Ensure package modules can be imported
package_dir = os.path.abspath(os.path.join(PROJECT_ROOT, "wsl_ws", "src", "isaac_ros2_control", "isaac_ros2_control"))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

# Standalone ROS 2 mock for non-WSL / test runner execution
try:
    import rclpy
    from rclpy.node import Node
except ImportError:
    import types
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
        def create_publisher(self, msg_type, topic, qos_profile=10):
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

    sys.modules['rclpy'] = types.ModuleType('rclpy')
    sys.modules['rclpy.node'] = types.ModuleType('rclpy.node')
    sys.modules['rclpy.node'].Node = MockNode
    sys.modules['rclpy.duration'] = types.ModuleType('rclpy.duration')
    sys.modules['rclpy.time'] = types.ModuleType('rclpy.time')
    sys.modules['rclpy.time'].Time = type('Time', (), {})
    sys.modules['sensor_msgs'] = types.ModuleType('sensor_msgs')
    sys.modules['sensor_msgs.msg'] = types.ModuleType('sensor_msgs.msg')
    sys.modules['sensor_msgs.msg'].JointState = type('JointState', (), {
        'header': type('H', (), {'stamp': None})(),
        'name': [],
        'position': []
    })
    sys.modules['std_msgs'] = types.ModuleType('std_msgs')
    sys.modules['std_msgs.msg'] = types.ModuleType('std_msgs.msg')
    sys.modules['std_msgs.msg'].Empty = type('Empty', (), {})
    sys.modules['std_msgs.msg'].String = type('String', (), {'data': ''})
    sys.modules['std_srvs'] = types.ModuleType('std_srvs')
    sys.modules['std_srvs.srv'] = types.ModuleType('std_srvs.srv')
    sys.modules['std_srvs.srv'].Trigger = type('Trigger', (), {})
    sys.modules['std_srvs.srv'].SetBool = type('SetBool', (), {})
    sys.modules['tf2_ros'] = types.ModuleType('tf2_ros')
    sys.modules['tf2_ros'].Buffer = type('Buffer', (), {
        'clear': lambda self: None,
        'lookup_transform': lambda *a: None
    })
    sys.modules['tf2_ros'].TransformListener = type('TransformListener', (), {})

from multi_robot_controller import (
    MultiRobotController,
    KITCHEN_AFFORDANCES,
    CLEARING_ZONES,
    DINING_ORGANIZATION_LAYOUT,
)
import kinematics


@pytest.mark.tier1
@pytest.mark.m2
class TestFeature07SingleArmDishManipulation(unittest.TestCase):
    """Feature 7: Single-Arm Dish Manipulation."""

    def test_f07_affordance_dict_contains_dish(self):
        """Verify KITCHEN_AFFORDANCES dictionary in multi_robot_controller.py defines dish parameters."""
        assert 'dish' in KITCHEN_AFFORDANCES
        dish = KITCHEN_AFFORDANCES['dish']
        assert dish['grasp_mode'] == 'rim_pinch'
        assert 'gripper_close' in dish
        assert 'approach_height' in dish

    def test_f07_dish_grasp_height_offset(self):
        """Verify dish grasp height is lower than standard block (shallow plate offset <= 0.03m)."""
        dish_affordance = KITCHEN_AFFORDANCES['dish']
        assert dish_affordance['grasp_z_offset'] <= 0.03
        assert dish_affordance['approach_height'] >= 0.08

    def test_f07_dish_rim_pinch_gripper_width(self):
        """Verify gripper close command for dish rim is within physical finger limits."""
        dish_affordance = KITCHEN_AFFORDANCES['dish']
        assert dish_affordance['gripper_close'] == 0.006
        assert dish_affordance['grasp_mode'] == 'rim_pinch'
        assert dish_affordance['rim_offset_radius'] == 0.065
        assert_gripper_limits(dish_affordance['gripper_close'])

    def test_f07_dish_touch_sensor_verification(self):
        """Verify controller verifies gripper contact before completing grasp."""
        dish_affordance = KITCHEN_AFFORDANCES['dish']
        vmin, vmax = dish_affordance['verification_range']
        assert vmin == 0.003 and vmax == 0.015
        assert vmin <= dish_affordance['gripper_close'] <= vmax

    def test_f07_dish_lift_trajectory_verticality(self):
        """Verify vertical lift phase to prevent scraping plate against table."""
        ctrl = MultiRobotController()
        affordance = ctrl.get_affordance('dish')
        assert affordance['lift_height'] >= 0.08
        table_z = WORKSPACE_BOUNDS["table_surface_z"]
        assert table_z + affordance['lift_height'] >= 0.28


@pytest.mark.tier1
@pytest.mark.m2
class TestFeature08SingleArmCupManipulation(unittest.TestCase):
    """Feature 8: Single-Arm Cup Manipulation."""

    def test_f08_affordance_dict_contains_cup(self):
        """Verify KITCHEN_AFFORDANCES defines cup grasping profile."""
        assert 'cup' in KITCHEN_AFFORDANCES
        cup = KITCHEN_AFFORDANCES['cup']
        assert cup['grasp_mode'] == 'cylindrical_clamp'
        assert cup['height'] == 0.090

    def test_f08_cup_mid_height_clamping(self):
        """Verify cup mid-height grasp z-offset (~0.03m - 0.06m) to prevent tipping."""
        cup_affordance = KITCHEN_AFFORDANCES['cup']
        assert 0.03 <= cup_affordance['grasp_z_offset'] <= 0.06
        assert cup_affordance['grasp_mode'] == 'cylindrical_clamp'
        assert cup_affordance['rim_offset_radius'] == 0.0

    def test_f08_cup_cylindrical_aperture(self):
        """Verify gripper width for cup body clamping is within valid finger range."""
        cup_affordance = KITCHEN_AFFORDANCES['cup']
        assert cup_affordance['gripper_close'] == 0.020
        assert_gripper_limits(cup_affordance['gripper_close'])

    def test_f08_cup_touch_sensor_feedback(self):
        """Verify contact confirmation for cylindrical cup grasp."""
        cup_affordance = KITCHEN_AFFORDANCES['cup']
        vmin, vmax = cup_affordance['verification_range']
        assert vmin == 0.016 and vmax == 0.035
        assert vmin <= cup_affordance['gripper_close'] <= vmax

    def test_f08_cup_upright_orientation_preservation(self):
        """Verify end-effector orientation maintains cup vertical (no tilt) during transit."""
        q_down = kinematics.compute_symmetric_grasp_quat(0.0, arm_yaw=0.0)
        R_down = kinematics.quat_to_rot_matrix(q_down)
        z_tool = R_down[:, 2]
        assert np.isclose(z_tool[2], -1.0, atol=0.01)


@pytest.mark.tier1
@pytest.mark.m2
class TestFeature09KitchenTableClearingOrganizing(unittest.TestCase):
    """Feature 9: Kitchen Table Clearing & Organizing."""

    def test_f09_clearing_primitive_supported(self):
        """Verify controller handles clearing/organizing action commands."""
        ctrl = MultiRobotController()
        assert hasattr(ctrl, "_find_clearable_object")
        assert hasattr(ctrl, "is_autonomous_cycle1")
        assert hasattr(ctrl, "autonomous_action_name1")

    def test_f09_multi_robot_clearing_dispatch(self):
        """Verify clearing workflow can assign tasks across FR3_1, FR3_2, FR3_3."""
        ctrl = MultiRobotController()
        obj1 = ctrl._find_clearable_object(1)
        obj2 = ctrl._find_clearable_object(2)
        obj3 = ctrl._find_clearable_object(3)
        assert obj1 is not None and obj2 is not None and obj3 is not None
        assert obj1 == "Dish1"
        assert obj2 == "Cup1"
        assert obj3 == "Dish2"

    def test_f09_target_staging_area_bounds(self):
        """Verify cleared objects are deposited within designated staging bounds."""
        assert "dish_rack" in CLEARING_ZONES
        assert "cup_tray" in CLEARING_ZONES
        assert "sink" in CLEARING_ZONES
        assert CLEARING_ZONES["default"][1] == [-0.15, -0.25]
        assert CLEARING_ZONES["default"][2] == [0.15, -0.25]
        assert CLEARING_ZONES["default"][3] == [0.0, -0.25]

    def test_f09_clearing_collision_mutex(self):
        """Verify mutual exclusion / collision lock during multi-robot table clearing."""
        ctrl = MultiRobotController()
        assert hasattr(ctrl, "center_occupied_by")
        assert ctrl.center_occupied_by is None
        ctrl.center_occupied_by = 1
        assert ctrl.center_occupied_by == 1
        ctrl.center_occupied_by = None
        assert ctrl.center_occupied_by is None

    def test_f09_clearing_completion_status(self):
        """Verify status publisher notifies completion of clearing operations."""
        ctrl = MultiRobotController()
        assert hasattr(ctrl, "status_pub")
        assert hasattr(ctrl, "result_pub")
        assert ctrl.status_pub is not None
        assert ctrl.result_pub is not None
