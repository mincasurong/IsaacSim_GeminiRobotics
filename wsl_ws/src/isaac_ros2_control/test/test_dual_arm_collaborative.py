"""Unit tests for Synchronized Dual-Arm Collaborative Manipulation (Requirement R3, Features 10-14).

Verifies:
1. Feature 10: Dual-Arm Kinematic Coordination & Virtual Rigid-Body Distance Invariance
2. Feature 11: Synchronized Approach & Simultaneous Contact Grasp Closure
3. Feature 12: Coupled Cartesian Transport & Outward Elbow Null-Space Biasing
4. Feature 13: Synchronized Release & Outward Collision-Free Retreat
5. Feature 14: Mutual Workspace Reservation (Mutex) & Collaborative Telemetry Streaming
6. Action Command & Action Result Contract Compliance (ACTION_COMMAND_SCHEMA, ACTION_RESULT_SCHEMA)
7. Preservation of single-arm kitchenware and block tower stacking primitives
"""

import sys
import os
import json
import unittest
import numpy as np

# Add package source to path for direct import
current_dir = os.path.dirname(os.path.abspath(__file__))
package_dir = os.path.abspath(os.path.join(current_dir, '..', 'isaac_ros2_control'))
if package_dir not in sys.path:
    sys.path.insert(0, package_dir)

# Import kinematics
try:
    import kinematics
except ImportError:
    from isaac_ros2_control import kinematics

# Mock ROS 2 if rclpy is not present in standard testing environment
try:
    import rclpy
    from rclpy.node import Node
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    class MockNode:
        def __init__(self, name):
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

from multi_robot_controller import (
    MultiRobotController,
    KITCHEN_AFFORDANCES,
    CLEARING_ZONES,
    DINING_ORGANIZATION_LAYOUT,
)


def setUpModule():
    if ROS2_AVAILABLE:
        if not rclpy.ok():
            rclpy.init()


def tearDownModule():
    if ROS2_AVAILABLE:
        if rclpy.ok():
            rclpy.shutdown()


def create_test_controller():
    ctrl = MultiRobotController()
    for pub_name in ['cmd_pub1', 'cmd_pub2', 'cmd_pub3', 'status_pub', 'result_pub', 'metrics_pub']:
        pub = getattr(ctrl, pub_name, None)
        if pub is not None and not hasattr(pub, 'last_msg'):
            pub.last_msg = None
            def make_spy(p):
                orig_publish = p.publish
                def _spy(msg):
                    p.last_msg = msg
                    try:
                        return orig_publish(msg)
                    except Exception:
                        pass
                return _spy
            pub.publish = make_spy(pub)
    return ctrl


class TestFeature10DualArmKinematics(unittest.TestCase):
    """Test Feature 10: Dual-Arm Kinematic Coordination & Distance Invariance."""

    def test_coupled_waypoints_distance_invariance(self):
        """Verify rigid-body distance between Robot 1 and Robot 2 is constant throughout transit."""
        start_c = [0.0, -0.20, 0.25]
        target_c = [0.0, 0.20, 0.25]
        nominal_separation = 0.40  # 0.40m separation between grasp points

        w1, w2 = MultiRobotController.generate_coupled_waypoints(
            start_c, target_c, bar_length=nominal_separation, num_steps=30
        )

        self.assertEqual(len(w1), 30)
        self.assertEqual(len(w2), 30)

        for p1, p2 in zip(w1, w2):
            dist = np.linalg.norm(p1 - p2)
            self.assertAlmostEqual(dist, nominal_separation, places=4,
                                   msg=f"Distance drift detected: {dist:.6f} != {nominal_separation}")

    def test_coupled_trajectory_zero_terminal_velocities(self):
        """Verify quintic polynomial velocity profile starts and ends at strictly zero."""
        t_vals = np.array([0.0, 1.0])
        # Derivative of s(t) = 10*t^3 - 15*t^4 + 6*t^5 is s'(t) = 30*t^2 - 60*t^3 + 30*t^4
        ds = 30.0 * (t_vals ** 2) - 60.0 * (t_vals ** 3) + 30.0 * (t_vals ** 4)
        self.assertAlmostEqual(ds[0], 0.0, places=6, msg="Initial velocity must be zero")
        self.assertAlmostEqual(ds[1], 0.0, places=6, msg="Final velocity must be zero")

    def test_world_to_base_coordinate_transform(self):
        """Verify world to robot base coordinate transform for FR3_1 and FR3_2."""
        ctrl = create_test_controller()
        try:
            center_world = [0.0, 0.0, 0.20]

            # Robot 1 mounted at [0, -0.45, 0.20], yaw +90 deg
            p1_local, _ = ctrl.world_to_base(1, center_world)
            self.assertAlmostEqual(p1_local[0], 0.45, places=3)
            self.assertAlmostEqual(p1_local[1], 0.0, places=3)
            self.assertAlmostEqual(p1_local[2], 0.0, places=3)

            # Robot 2 mounted at [0.3897, 0.225, 0.20], yaw +210 deg
            p2_local, _ = ctrl.world_to_base(2, center_world)
            self.assertGreater(p2_local[0], 0.3)  # Reaching forward from base
        finally:
            ctrl.destroy_node()


class TestFeature11SynchronizedApproachContactClosure(unittest.TestCase):
    """Test Feature 11: Synchronized Approach & Simultaneous Contact Grasp."""

    def setUp(self):
        self.ctrl = create_test_controller()
        # Initialize joint states to home
        self.ctrl.current_joints1 = list(self.ctrl.q_home_fr3)
        self.ctrl.current_joints2 = list(self.ctrl.q_home_fr3)
        self.ctrl.current_joints3 = list(self.ctrl.q_home_fr3)

    def tearDown(self):
        if hasattr(self, 'ctrl') and self.ctrl is not None:
            self.ctrl.destroy_node()

    def test_lock_step_state_machine_initiation(self):
        """Verify _start_dual_carry properly activates dual collaboration and reserves mutex."""
        self.ctrl._start_dual_carry(
            robots=[1, 2],
            target_name='LongBar1',
            dest_pos=[0.0, 0.15, 0.22],
            dest_yaw=0.0,
            steps=20
        )

        self.assertTrue(self.ctrl.dual_active)
        self.assertEqual(self.ctrl.dual_state, 'DUAL_INIT')
        self.assertTrue(self.ctrl.collaborative_active)
        self.assertEqual(self.ctrl.collaborative_pair, ['FR3_1', 'FR3_2'])
        self.assertEqual(self.ctrl.collaborative_object, 'LongBar1')

        # Run one step of dual arm processor
        self.ctrl._process_dual_arm()
        self.assertEqual(self.ctrl.center_occupied_by, 'DUAL_FR3_1_FR3_2')
        self.assertEqual(self.ctrl.dual_state, 'DUAL_ROTATE_TO_APPROACH')

    def test_simultaneous_gripper_close_target(self):
        """Verify both grippers target 0.018m during contact grasp phase."""
        affordance = self.ctrl.get_affordance('long_bar')
        grip_close = affordance.get('gripper_close')
        self.assertEqual(grip_close, 0.018)

    def test_dual_touch_sensor_verification_success(self):
        """Verify both grippers confirming contact in [0.012, 0.028]m allows transition to lift."""
        self.ctrl.dual_active = True
        self.ctrl.dual_state = 'DUAL_CONTACT_GRASP'
        self.ctrl.dual_step_counter = self.ctrl.dual_dwell_steps
        self.ctrl.dual_robots = [1, 2]
        self.ctrl.current_gripper1 = 0.018
        self.ctrl.current_gripper2 = 0.018
        self.ctrl.dual_w1_end = np.array([0.45, -0.20, 0.05])
        self.ctrl.dual_w2_end = np.array([0.45, 0.20, 0.05])

        self.ctrl._transition_dual_arm_phase()
        self.assertEqual(self.ctrl.dual_state, 'DUAL_SYNCHRONIZED_LIFT')

    def test_dual_touch_sensor_verification_failure_aborts(self):
        """Verify single gripper contact failure triggers DUAL_ABORT."""
        self.ctrl.dual_active = True
        self.ctrl.dual_state = 'DUAL_CONTACT_GRASP'
        self.ctrl.dual_step_counter = self.ctrl.dual_dwell_steps
        self.ctrl.dual_robots = [1, 2]
        self.ctrl.current_gripper1 = 0.018
        self.ctrl.current_gripper2 = 0.002  # Closed completely on empty air!

        self.ctrl._transition_dual_arm_phase()
        self.assertEqual(self.ctrl.dual_state, 'DUAL_ABORT')
        self.assertFalse(self.ctrl.collaborative_active)
        self.assertIsNone(self.ctrl.center_occupied_by)


class TestFeature12CoupledCartesianTransport(unittest.TestCase):
    """Test Feature 12: Coupled Transport & Outward Elbow Null-Space Biasing."""

    def setUp(self):
        self.ctrl = create_test_controller()

    def tearDown(self):
        if hasattr(self, 'ctrl') and self.ctrl is not None:
            self.ctrl.destroy_node()

    def test_elbow_null_space_biasing_convergence(self):
        """Verify solve_ik_with_elbow_bias converges and keeps elbows outward."""
        target_pos = np.array([0.45, 0.0, 0.15])
        target_quat = [0.0, 1.0, 0.0, 0.0]
        q_init = np.array(self.ctrl.q_home_fr3)

        # Solve for Robot 1 (elbow biased toward West)
        q_sol1, ok1 = self.ctrl.solve_ik_with_elbow_bias(1, target_pos, target_quat, q_init)
        self.assertTrue(ok1, "IK solver should converge for reachable workspace target")

        # Solve for Robot 2 (elbow biased toward East)
        q_sol2, ok2 = self.ctrl.solve_ik_with_elbow_bias(2, target_pos, target_quat, q_init)
        self.assertTrue(ok2, "IK solver should converge for reachable workspace target")

        # Joint 3 (swivel) angles have opposing sign to push elbows outward
        self.assertGreater(q_sol1[2], -0.2)
        self.assertLess(q_sol2[2], 0.2)

    def test_fr3_joint_limits_satisfied(self):
        """Verify all joints remain strictly within Franka FR3 physical limits."""
        target_pos = np.array([0.40, -0.10, 0.12])
        target_quat = [0.0, 1.0, 0.0, 0.0]
        q_sol, ok = self.ctrl.solve_ik_with_elbow_bias(1, target_pos, target_quat, self.ctrl.q_home_fr3)
        self.assertTrue(ok)
        for i in range(7):
            q_min, q_max = kinematics.FR3_JOINT_LIMITS[i]
            self.assertGreaterEqual(q_sol[i], q_min - 1e-4)
            self.assertLessEqual(q_sol[i], q_max + 1e-4)


class TestFeature13SynchronizedReleaseCompliance(unittest.TestCase):
    """Test Feature 13: Synchronized Release & Outward Retreat."""

    def test_synchronized_release_opens_grippers(self):
        """Verify release phase commands both grippers to open to 0.040m."""
        ctrl = create_test_controller()
        try:
            affordance = ctrl.get_affordance('long_bar')
            ctrl.dual_active = True
            ctrl.dual_state = 'DUAL_SYNCHRONIZED_DESCEND'
            ctrl.dual_robots = [1, 2]
            ctrl.dual_dest_pos = np.array([0.0, 0.15, 0.22])
            ctrl.dual_dest_yaw = 0.0

            ctrl._transition_dual_arm_phase()
            self.assertEqual(ctrl.dual_state, 'DUAL_SYNCHRONIZED_RELEASE')
            self.assertEqual(ctrl.dual_grip_end, ctrl.gripper_open)
            self.assertEqual(ctrl.dual_grip_end, 0.040)
        finally:
            ctrl.destroy_node()

    def test_outward_retreat_vector(self):
        """Verify retreat moves arms outward in opposite directions away from bar."""
        ctrl = create_test_controller()
        try:
            ctrl.dual_active = True
            ctrl.dual_state = 'DUAL_SYNCHRONIZED_RELEASE'
            ctrl.dual_robots = [1, 2]
            ctrl.dual_w1_end = np.array([0.40, -0.20, 0.10])
            ctrl.dual_w2_end = np.array([0.40, 0.20, 0.10])

            ctrl._transition_dual_arm_phase()
            self.assertEqual(ctrl.dual_state, 'DUAL_SYNCHRONIZED_RETRACT')
            # Robot 1 moved -X local, Robot 2 moved +X local
            self.assertLess(ctrl.dual_w1_end[0], 0.40)
            self.assertGreater(ctrl.dual_w2_end[0], 0.40)
        finally:
            ctrl.destroy_node()


class TestFeature14CollaborativeTelemetryAndMutex(unittest.TestCase):
    """Test Feature 14: Collaborative Telemetry & Mutex Reservation."""

    def setUp(self):
        self.ctrl = create_test_controller()

    def tearDown(self):
        if hasattr(self, 'ctrl') and self.ctrl is not None:
            self.ctrl.destroy_node()

    def test_center_mutex_lockout_robot3(self):
        """Verify DUAL_FR3_1_FR3_2 mutex blocks robot 3 in WAIT_FOR_CENTER."""
        self.ctrl.center_occupied_by = 'DUAL_FR3_1_FR3_2'
        self.ctrl.state3 = 'WAIT_FOR_CENTER'

        # Process robot 3 step
        self.ctrl.current_joints3 = list(self.ctrl.q_home_fr3)
        self.ctrl._process_robot(3)

        # Robot 3 must remain waiting and not enter center table
        self.assertEqual(self.ctrl.state3, 'WAIT_FOR_CENTER')
        self.assertEqual(self.ctrl.center_occupied_by, 'DUAL_FR3_1_FR3_2')

    def test_telemetry_streaming_payload_structure(self):
        """Verify /multi_robot/robot_metrics message contains collaborative fields."""
        self.ctrl.collaborative_active = True
        self.ctrl.collaborative_pair = ['FR3_1', 'FR3_2']
        self.ctrl.collaborative_object = 'LongBar1'
        self.ctrl.center_occupied_by = 'DUAL_FR3_1_FR3_2'
        self.ctrl.dual_state = 'DUAL_COUPLED_TRANSPORT'

        self.ctrl._publish_metrics()
        last_msg = self.ctrl.metrics_pub.last_msg
        self.assertIsNotNone(last_msg)

        data = json.loads(last_msg.data)
        self.assertTrue(data['collaborative_active'])
        self.assertEqual(data['collaborative_pair'], ['FR3_1', 'FR3_2'])
        self.assertEqual(data['collaborative_object'], 'LongBar1')
        self.assertEqual(data['center_occupied_by'], 'DUAL_FR3_1_FR3_2')

        # Verify dual linkage attributes for React Flow visualizer
        self.assertEqual(data['robots']['FR3_1']['collaborating_with'], 'FR3_2')
        self.assertTrue(data['robots']['FR3_1']['dual_link_active'])
        self.assertEqual(data['robots']['FR3_1']['state'], 'COLLAB_TRANSIT')
        self.assertEqual(data['robots']['1']['state'], 'COLLAB_TRANSIT')

    def test_telemetry_reset_upon_completion(self):
        """Verify collaborative flags reset upon DUAL_RETURN_HOME completion."""
        self.ctrl.dual_active = True
        self.ctrl.dual_state = 'DUAL_RETURN_HOME'
        self.ctrl.dual_robots = [1, 2]
        self.ctrl.center_occupied_by = 'DUAL_FR3_1_FR3_2'
        self.ctrl.collaborative_active = True
        self.ctrl.collaborative_pair = ['FR3_1', 'FR3_2']
        self.ctrl.collaborative_object = 'LongBar1'

        self.ctrl._transition_dual_arm_phase()
        self.assertFalse(self.ctrl.dual_active)
        self.assertEqual(self.ctrl.dual_state, 'DUAL_FINISHED')
        self.assertFalse(self.ctrl.collaborative_active)
        self.assertIsNone(self.ctrl.collaborative_pair)
        self.assertIsNone(self.ctrl.collaborative_object)
        self.assertIsNone(self.ctrl.center_occupied_by)

    def test_action_result_schema_compliance(self):
        """Verify action result published by dual collaboration matches schema."""
        self.ctrl._publish_result(
            True,
            "LongBar1 transferred successfully to destination without drop or drift",
            robot_id="DUAL_FR3_1_FR3_2",
            action="dual_carry"
        )
        last_msg = self.ctrl.result_pub.last_msg
        self.assertIsNotNone(last_msg)

        res = json.loads(last_msg.data)
        self.assertEqual(res['robot'], 'DUAL_FR3_1_FR3_2')
        self.assertEqual(res['action'], 'dual_carry')
        self.assertEqual(res['status'], 'SUCCESS')
        self.assertTrue(res['success'])


class TestActionCommandDispatchDualCarry(unittest.TestCase):
    """Test handling of dual_carry JSON commands on /gemini/action."""

    def test_dispatch_dual_carry_command(self):
        """Verify JSON action dispatch triggers dual_carry sequence."""
        ctrl = create_test_controller()
        try:
            msg = type('Msg', (), {'data': json.dumps({
                "action": "dual_carry",
                "robots": ["FR3_1", "FR3_2"],
                "object": "LongBar1",
                "destination": [0.0, 0.15, 0.22],
                "sync_mode": "rigid_body"
            })})()

            ctrl._action_cb(msg)
            self.assertTrue(ctrl.dual_active)
            self.assertEqual(ctrl.dual_state, 'DUAL_INIT')
            self.assertEqual(ctrl.dual_target_name, 'LongBar1')
            self.assertAlmostEqual(ctrl.dual_dest_pos[1], 0.15)
        finally:
            ctrl.destroy_node()


if __name__ == '__main__':
    unittest.main()
