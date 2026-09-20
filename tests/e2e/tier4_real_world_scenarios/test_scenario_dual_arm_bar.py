"""Tier 4 Real-World Scenario: 🤝 Dual-Arm Bar Transfer.

End-to-end collaborative task flow executing genuine MultiRobotController and VLA logic:
1. Perception & Reasoning: Detect oversized long bar, classify affordance via gemini_utils and taxonomy.
2. Action Dispatch: Issue dual_carry command to MultiRobotController, verifying state machine initialization and mutex reservation.
3. Lock-step Grasp: Execute MultiRobotController lock-step phases with dual touch verification window and abort handling.
4. Coupled Transport: Execute MultiRobotController.generate_coupled_waypoints, DLS numerical IK with elbow null-space biasing, and verify live /multi_robot/robot_metrics telemetry.
5. Synchronized Release: Execute synchronized release, outward retreat vector, and verify published /gemini/action_result payload.
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
from multi_robot_controller import MultiRobotController, KITCHEN_AFFORDANCES

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
    TELEMETRY_SCHEMA
)
from ..framework.assertions import (
    assert_joint_limits,
    assert_rigid_body_distance,
    assert_valid_json_schema
)


@pytest.mark.tier4
@pytest.mark.m3
class TestScenarioDualArmBarTransfer(unittest.TestCase):
    """End-to-end real-world scenario: Dual-Arm Long Bar Collaborative Transfer."""

    def setUp(self):
        self.ctrl = MultiRobotController()
        self.ctrl.current_joints1 = list(self.ctrl.q_home_fr3)
        self.ctrl.current_joints2 = list(self.ctrl.q_home_fr3)
        self.ctrl.current_joints3 = list(self.ctrl.q_home_fr3)

    def test_s2_perception_and_dual_arm_classification(self):
        """Scenario 2 - Step 1: Detect oversized long bar and classify affordance using genuine VLA utility."""
        detected_label = "oversized long bar"
        resolved_key = gemini_utils.resolve_object_key(detected_label)
        self.assertEqual(resolved_key, "LongBar1", "Must resolve to canonical prim LongBar1")

        obj_type = gemini_utils.get_object_type(resolved_key)
        self.assertEqual(obj_type, "long_bar")

        is_dual = gemini_utils.is_dual_arm_object(resolved_key)
        self.assertTrue(is_dual, "Oversized long bar must require dual-arm manipulation")

        affordance = self.ctrl.get_affordance('long_bar')
        self.assertEqual(affordance['grasp_mode'], 'dual_clamping')
        self.assertEqual(affordance['gripper_close'], 0.018)

    def test_s2_dual_carry_command_dispatch(self):
        """Scenario 2 - Step 2: Dispatch dual_carry action command to multi_robot_controller."""
        cmd_payload = {
            "action": "dual_carry",
            "robots": ["FR3_1", "FR3_2"],
            "object": "LongBar1",
            "destination": [0.0, 0.15, 0.22],
            "sync_mode": "rigid_body",
            "speed": "fast"
        }
        assert_valid_json_schema(cmd_payload, ACTION_COMMAND_SCHEMA)

        # Dispatch through controller action callback
        msg = type('Msg', (), {'data': json.dumps(cmd_payload)})()
        self.ctrl._action_cb(msg)

        self.assertTrue(self.ctrl.dual_active)
        self.assertEqual(self.ctrl.dual_state, 'DUAL_INIT')
        self.assertTrue(self.ctrl.collaborative_active)
        self.assertEqual(self.ctrl.collaborative_pair, ['FR3_1', 'FR3_2'])
        self.assertEqual(self.ctrl.collaborative_object, 'LongBar1')
        self.assertEqual(self.ctrl.dual_steps_per_phase, 20)  # speed='fast' maps to 20 steps

        # Run lock-step cycle: reserves central table mutex
        self.ctrl._process_dual_arm()
        self.assertEqual(self.ctrl.center_occupied_by, 'DUAL_FR3_1_FR3_2')
        self.assertEqual(self.ctrl.dual_state, 'DUAL_ROTATE_TO_APPROACH')

    def test_s2_synchronized_grasp_phase_execution(self):
        """Scenario 2 - Step 3: Lock-step synchronized approach and simultaneous contact closure with touch verification."""
        affordance = self.ctrl.get_affordance('long_bar')
        vmin, vmax = affordance['verification_range']
        grip_close = affordance['gripper_close']

        # Setup state machine in DUAL_CONTACT_GRASP
        self.ctrl.dual_active = True
        self.ctrl.dual_state = 'DUAL_CONTACT_GRASP'
        self.ctrl.dual_step_counter = self.ctrl.dual_dwell_steps
        self.ctrl.dual_robots = [1, 2]
        self.ctrl.dual_w1_end = np.array([0.45, -0.20, 0.05])
        self.ctrl.dual_w2_end = np.array([0.45, 0.20, 0.05])

        # Test Case 3A: Both robots confirm contact within physical verification range [0.012, 0.028]m
        self.ctrl.current_gripper1 = grip_close
        self.ctrl.current_gripper2 = grip_close
        self.assertTrue(vmin <= self.ctrl.current_gripper1 <= vmax)
        self.assertTrue(vmin <= self.ctrl.current_gripper2 <= vmax)

        self.ctrl._transition_dual_arm_phase()
        self.assertEqual(self.ctrl.dual_state, 'DUAL_SYNCHRONIZED_LIFT',
                         "Simultaneous contact confirmation must advance to DUAL_SYNCHRONIZED_LIFT")

        # Test Case 3B: Single arm contact failure triggers DUAL_ABORT safety fallback
        self.ctrl.dual_state = 'DUAL_CONTACT_GRASP'
        self.ctrl.dual_step_counter = self.ctrl.dual_dwell_steps
        self.ctrl.current_gripper1 = grip_close
        self.ctrl.current_gripper2 = 0.002  # Finger closed on air (missed grasp)

        self.ctrl._transition_dual_arm_phase()
        self.assertEqual(self.ctrl.dual_state, 'DUAL_ABORT', "Contact failure must abort dual transport")
        self.assertFalse(self.ctrl.collaborative_active)
        self.assertIsNone(self.ctrl.center_occupied_by)

    def test_s2_coupled_transport_and_telemetry_streaming(self):
        """Scenario 2 - Step 4: Coupled transport maintaining distance invariance and streaming telemetry."""
        nominal_sep = self.ctrl.dual_grasp_separation  # 0.40m
        start_c = [0.0, -0.15, 0.25]
        target_c = [0.0, 0.15, 0.25]

        # 1. Verify rigid-body distance invariance from controller trajectory generator
        w1, w2 = MultiRobotController.generate_coupled_waypoints(start_c, target_c, bar_length=nominal_sep, num_steps=30)
        self.assertEqual(len(w1), 30)
        self.assertEqual(len(w2), 30)
        for p1, p2 in zip(w1, w2):
            assert_rigid_body_distance(p1, p2, nominal_sep, tol=0.001)

        # 2. Verify DLS IK solver convergence with outward elbow biasing
        q_init = np.array(self.ctrl.q_home_fr3)
        target_quat = [0.0, 1.0, 0.0, 0.0]
        p1_loc, _ = self.ctrl.world_to_base(1, w1[15])
        p2_loc, _ = self.ctrl.world_to_base(2, w2[15])
        q_sol1, ok1 = self.ctrl.solve_ik_with_elbow_bias(1, p1_loc, target_quat, q_init)
        q_sol2, ok2 = self.ctrl.solve_ik_with_elbow_bias(2, p2_loc, target_quat, q_init)
        self.assertTrue(ok1, "Robot 1 IK must converge during transit")
        self.assertTrue(ok2, "Robot 2 IK must converge during transit")
        assert_joint_limits(q_sol1)
        assert_joint_limits(q_sol2)

        # 3. Verify live collaborative telemetry streaming payload on /multi_robot/robot_metrics
        self.ctrl.collaborative_active = True
        self.ctrl.collaborative_pair = ['FR3_1', 'FR3_2']
        self.ctrl.collaborative_object = 'LongBar1'
        self.ctrl.center_occupied_by = 'DUAL_FR3_1_FR3_2'
        self.ctrl.dual_state = 'DUAL_COUPLED_TRANSPORT'

        self.ctrl._publish_metrics()
        self.assertIsNotNone(self.ctrl.metrics_pub.last_msg)
        telemetry_data = json.loads(self.ctrl.metrics_pub.last_msg.data)
        assert_valid_json_schema(telemetry_data, TELEMETRY_SCHEMA)
        self.assertTrue(telemetry_data["collaborative_active"])
        self.assertEqual(telemetry_data["collaborative_pair"], ["FR3_1", "FR3_2"])
        self.assertEqual(telemetry_data["collaborative_object"], "LongBar1")
        self.assertEqual(telemetry_data["center_occupied_by"], "DUAL_FR3_1_FR3_2")
        self.assertEqual(telemetry_data["robots"]["FR3_1"]["state"], "COLLAB_TRANSIT")
        self.assertTrue(telemetry_data["robots"]["FR3_1"]["dual_link_active"])
        self.assertEqual(telemetry_data["robots"]["FR3_1"]["collaborating_with"], "FR3_2")

    def test_s2_synchronized_release_and_completion(self):
        """Scenario 2 - Step 5: Compliant release, outward retreat, and action result SUCCESS."""
        # 1. Descend to placement surface
        self.ctrl.dual_active = True
        self.ctrl.dual_state = 'DUAL_SYNCHRONIZED_DESCEND'
        self.ctrl.dual_robots = [1, 2]
        self.ctrl.dual_dest_pos = np.array([0.0, 0.15, 0.22])
        self.ctrl.dual_dest_yaw = 0.0

        # 2. Release phase: both grippers open to 0.040m
        self.ctrl._transition_dual_arm_phase()
        self.assertEqual(self.ctrl.dual_state, 'DUAL_SYNCHRONIZED_RELEASE')
        self.assertEqual(self.ctrl.dual_grip_end, self.ctrl.gripper_open)
        self.assertEqual(self.ctrl.dual_grip_end, 0.040)

        # 3. Retract phase: outward collision-free retreat
        self.ctrl.dual_w1_end = np.array([0.40, -0.20, 0.10])
        self.ctrl.dual_w2_end = np.array([0.40, 0.20, 0.10])
        self.ctrl._transition_dual_arm_phase()
        self.assertEqual(self.ctrl.dual_state, 'DUAL_SYNCHRONIZED_RETRACT')
        self.assertLess(self.ctrl.dual_w1_end[0], 0.40, "Robot 1 retreats in -X direction")
        self.assertGreater(self.ctrl.dual_w2_end[0], 0.40, "Robot 2 retreats in +X direction")

        # 4. Return home phase: resets flags and releases mutex
        self.ctrl._transition_dual_arm_phase()
        self.assertEqual(self.ctrl.dual_state, 'DUAL_RETURN_HOME')
        self.ctrl.center_occupied_by = 'DUAL_FR3_1_FR3_2'
        self.ctrl.collaborative_active = True
        self.ctrl.collaborative_pair = ['FR3_1', 'FR3_2']
        self.ctrl.collaborative_object = 'LongBar1'

        self.ctrl._transition_dual_arm_phase()
        self.assertEqual(self.ctrl.dual_state, 'DUAL_FINISHED')
        self.assertFalse(self.ctrl.dual_active)
        self.assertFalse(self.ctrl.collaborative_active)
        self.assertIsNone(self.ctrl.collaborative_pair)
        self.assertIsNone(self.ctrl.collaborative_object)
        self.assertIsNone(self.ctrl.center_occupied_by, "Central mutex must be released")

        # 5. Verify published /gemini/action_result payload
        self.assertIsNotNone(self.ctrl.result_pub.last_msg)
        action_result = json.loads(self.ctrl.result_pub.last_msg.data)
        assert_valid_json_schema(action_result, ACTION_RESULT_SCHEMA)
        self.assertEqual(action_result["robot"], "DUAL_FR3_1_FR3_2")
        self.assertEqual(action_result["action"], "dual_carry")
        self.assertEqual(action_result["status"], "SUCCESS")
        self.assertTrue(action_result["success"])
        self.assertIn("transferred successfully", action_result["message"])
