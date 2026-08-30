"""Multi-Robot Motion Planner & Controller for Isaac Sim.

Supports two operational modes:
1. 'rule_based' (default): Autonomous, deterministic multi-robot turn-based
   pick-and-place tower stacking using TF pose tracking and kinematics.
2. 'gemini': Dispatches primitives ('pick', 'place', 'go_home') orchestrated
   by Gemini Robotics-ER 2 VLM via ROS 2 actions/topics.
"""

import json
import time
import numpy as np
import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Empty, String
from std_srvs.srv import Trigger, SetBool
import tf2_ros

try:
    from isaac_ros2_control import kinematics
except ImportError:
    try:
        from . import kinematics
    except ImportError:
        import kinematics


class MultiRobotController(Node):
    """Unified Controller and Motion Planner for FR3_1, FR3_2, and FR3_3."""

    def __init__(self):
        super().__init__('multi_robot_controller')

        # Parameters
        self.declare_parameter('mode', 'rule_based')  # 'rule_based' or 'gemini'
        self.declare_parameter('tower_x', 0.0)
        self.declare_parameter('tower_y', 0.0)
        self.declare_parameter('block_height', 0.06)
        self.declare_parameter('hover_height', 0.10)
        self.declare_parameter('steps_per_phase', 10)
        self.declare_parameter('dwell_steps', 2)

        self.mode = self.get_parameter('mode').get_parameter_value().string_value
        self.stack_pos_world = [
            self.get_parameter('tower_x').get_parameter_value().double_value,
            self.get_parameter('tower_y').get_parameter_value().double_value
        ]
        self.block_height = self.get_parameter('block_height').get_parameter_value().double_value
        self.hover_height = self.get_parameter('hover_height').get_parameter_value().double_value
        self.steps_per_phase = self.get_parameter('steps_per_phase').get_parameter_value().integer_value
        self.dwell_steps = self.get_parameter('dwell_steps').get_parameter_value().integer_value

        # Publishers
        self.cmd_pub1 = self.create_publisher(JointState, '/fr3_1/joint_commands', 10)
        self.cmd_pub2 = self.create_publisher(JointState, '/fr3_2/joint_commands', 10)
        self.cmd_pub3 = self.create_publisher(JointState, '/fr3_3/joint_commands', 10)
        self.status_pub = self.create_publisher(String, '/multi_robot/status', 10)
        self.result_pub = self.create_publisher(String, '/gemini/action_result', 10)
        self.metrics_pub = self.create_publisher(String, '/multi_robot/robot_metrics', 10)

        # Subscribers
        self.state_sub1 = self.create_subscription(JointState, '/fr3_1/joint_states', self._state_cb1, 10)
        self.state_sub2 = self.create_subscription(JointState, '/fr3_2/joint_states', self._state_cb2, 10)
        self.state_sub3 = self.create_subscription(JointState, '/fr3_3/joint_states', self._state_cb3, 10)
        self.reset_sub = self.create_subscription(Empty, '/reset_simulation', self._reset_cb, 10)
        self.action_sub = self.create_subscription(String, '/gemini/action', self._action_cb, 10)

        # Services
        self.reset_srv = self.create_service(Trigger, '/multi_robot/reset', self._reset_srv_cb)
        self.mode_srv = self.create_service(SetBool, '/multi_robot/set_gemini_mode', self._set_gemini_mode_cb)

        # TF Buffer & Listener
        self.tf_buffer = tf2_ros.Buffer(node=self)
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # Robot Definitions & Joint Names
        self.joint_names_fr3 = [
            "fr3_joint1", "fr3_joint2", "fr3_joint3", "fr3_joint4",
            "fr3_joint5", "fr3_joint6", "fr3_joint7",
            "fr3_finger_joint1", "fr3_finger_joint2"
        ]

        self.q_home_fr3 = [1.5708, 0.0, 0.0, -1.5708, 0.0, 1.5708, 0.7854]

        # Tucked configuration: joints 2-7 only. Joint 1 is controlled independently.
        self.q_tuck_body = [-0.5, 0.0, -2.0, 0.0, 1.5, 0.7854]

        self.gripper_open = 0.04
        self.gripper_close = 0.015

        # Controller & Motion Planner State
        self.current_joints1 = None
        self.current_joints2 = None
        self.current_joints3 = None
        
        self.current_gripper1 = 0.0
        self.current_gripper2 = 0.0
        self.current_gripper3 = 0.0

        self.q_current1 = list(self.q_home_fr3)
        self.q_current2 = list(self.q_home_fr3)
        self.q_current3 = list(self.q_home_fr3)
        
        self.rotation_dir1 = 'shortest'
        self.rotation_dir2 = 'shortest'
        self.rotation_dir3 = 'shortest'

        self.state1 = 'INIT'
        self.state2 = 'INIT'
        self.state3 = 'INIT'

        self.block_index1 = 0
        self.block_index2 = 0
        self.block_index3 = 0

        self.step_counter1 = 0
        self.step_counter2 = 0
        self.step_counter3 = 0

        self.start_pos1 = None; self.end_pos1 = None
        self.start_pos2 = None; self.end_pos2 = None
        self.start_pos3 = None; self.end_pos3 = None

        self.start_quat1 = [0.0, 1.0, 0.0, 0.0]; self.end_quat1 = [0.0, 1.0, 0.0, 0.0]
        self.start_quat2 = [0.0, 1.0, 0.0, 0.0]; self.end_quat2 = [0.0, 1.0, 0.0, 0.0]
        self.start_quat3 = [0.0, 1.0, 0.0, 0.0]; self.end_quat3 = [0.0, 1.0, 0.0, 0.0]

        self.start_q1 = list(self.q_home_fr3); self.end_q1 = list(self.q_home_fr3)
        self.start_q2 = list(self.q_home_fr3); self.end_q2 = list(self.q_home_fr3)
        self.start_q3 = list(self.q_home_fr3); self.end_q3 = list(self.q_home_fr3)

        self.start_gripper1 = self.gripper_open; self.end_gripper1 = self.gripper_open
        self.start_gripper2 = self.gripper_open; self.end_gripper2 = self.gripper_open
        self.start_gripper3 = self.gripper_open; self.end_gripper3 = self.gripper_open

        self.tower_height = 0
        self.active_robot_id = 1
        
        self.active_target1 = None
        self.active_target2 = None
        self.active_target3 = None
        
        self.gemini_action1 = None
        self.gemini_action2 = None
        self.gemini_action3 = None
        self.center_occupied_by = None

        # Metrics & Utilization Tracking
        self._metrics_start_time = time.monotonic()
        self._robot_busy_time = {1: 0.0, 2: 0.0, 3: 0.0}
        self._robot_idle_time = {1: 0.0, 2: 0.0, 3: 0.0}
        self._robot_last_transition = {1: time.monotonic(), 2: time.monotonic(), 3: time.monotonic()}
        self._robot_was_busy = {1: False, 2: False, 3: False}
        self._tasks_completed = {1: 0, 2: 0, 3: 0}
        self._tasks_failed = {1: 0, 2: 0, 3: 0}

        # 50 Hz Control Loop Timer
        self.timer = self.create_timer(0.02, self._timer_callback)
        self.metrics_timer = self.create_timer(0.5, self._publish_metrics)

        self.get_logger().info(
            f"MultiRobotController initialized. Mode: [{self.mode.upper()}]. "
            "Waiting for joint states and TF frames..."
        )

    # Callbacks & ROS 2 Handlers

    def _state_cb1(self, msg):
        self.current_joints1 = msg.position
        for i in range(7):
            name = f"fr3_joint{i+1}"
            if name in msg.name:
                self.q_current1[i] = msg.position[msg.name.index(name)]
        if "fr3_finger_joint1" in msg.name:
            self.current_gripper1 = msg.position[msg.name.index("fr3_finger_joint1")]

    def _state_cb2(self, msg):
        self.current_joints2 = msg.position
        for i in range(7):
            name = f"fr3_joint{i+1}"
            if name in msg.name:
                self.q_current2[i] = msg.position[msg.name.index(name)]
        if "fr3_finger_joint1" in msg.name:
            self.current_gripper2 = msg.position[msg.name.index("fr3_finger_joint1")]

    def _state_cb3(self, msg):
        self.current_joints3 = msg.position
        for i in range(7):
            name = f"fr3_joint{i+1}"
            if name in msg.name:
                self.q_current3[i] = msg.position[msg.name.index(name)]
        if "fr3_finger_joint1" in msg.name:
            self.current_gripper3 = msg.position[msg.name.index("fr3_finger_joint1")]

    def _reset_cb(self, msg):
        self._execute_reset()

    def _reset_srv_cb(self, request, response):
        self._execute_reset()
        response.success = True
        response.message = "Controller reset successfully."
        return response

    def _set_gemini_mode_cb(self, request, response):
        self.mode = 'gemini' if request.data else 'rule_based'
        self.get_logger().info(f"Switched operational mode to: [{self.mode.upper()}]")
        response.success = True
        response.message = f"Mode set to {self.mode}"
        return response

    def _execute_reset(self):
        self.get_logger().info("[RESET] Resetting multi-robot controller and sequencer...")
        self.state1 = 'INIT'
        self.state2 = 'INIT'
        self.state3 = 'INIT'
        self.block_index1 = 0
        self.block_index2 = 0
        self.block_index3 = 0
        self.step_counter1 = 0
        self.step_counter2 = 0
        self.step_counter3 = 0
        self.q_current1 = list(self.q_home_fr3)
        self.q_current2 = list(self.q_home_fr3)
        self.q_current3 = list(self.q_home_fr3)
        self.tower_height = 0
        self.active_robot_id = 1
        
        self.active_target1 = None
        self.active_target2 = None
        self.active_target3 = None
        
        self.gemini_action1 = None
        self.gemini_action2 = None
        self.gemini_action3 = None
        
        self.center_occupied_by = None
        
        self._metrics_start_time = time.monotonic()
        self._robot_busy_time = {1: 0.0, 2: 0.0, 3: 0.0}
        self._robot_idle_time = {1: 0.0, 2: 0.0, 3: 0.0}
        self._robot_last_transition = {1: time.monotonic(), 2: time.monotonic(), 3: time.monotonic()}
        self._robot_was_busy = {1: False, 2: False, 3: False}
        self._tasks_completed = {1: 0, 2: 0, 3: 0}
        self._tasks_failed = {1: 0, 2: 0, 3: 0}

        try:
            self.tf_buffer.clear()
        except Exception:
            pass

    def _action_cb(self, msg):
        """Handle incoming Gemini VLM action commands."""
        self.get_logger().info(f"[GEMINI ACTION] Received: {msg.data}")
        self.mode = 'gemini'

        try:
            cmd = json.loads(msg.data)
            action = cmd.get('action', '').lower()
            robot_str = cmd.get('robot', '').upper()

            if 'FR3_1' in robot_str or 'ROBOT1' in robot_str or '1' in robot_str:
                r_id = 1
            elif 'FR3_2' in robot_str or 'ROBOT2' in robot_str or '2' in robot_str:
                r_id = 2
            elif 'FR3_3' in robot_str or 'ROBOT3' in robot_str or '3' in robot_str:
                r_id = 3
            elif action == 'verify_tower':
                # Special global action
                r_id = 'global'
            else:
                self._publish_result(False, f"Unknown robot identifier: {robot_str}")
                return

            if r_id != 'global':
                setattr(self, f'gemini_action{r_id}', action)

            if action == 'pick':
                target_label = cmd.get('target', '')
                block_name = self._resolve_block_name(target_label)
                if not block_name:
                    self._publish_result(False, f"Could not map target '{target_label}' to a block prim.", f"FR3_{r_id}")
                    return
                setattr(self, f'active_target{r_id}', block_name)
                
                # Dynamic Hyperparameters
                speed = cmd.get('speed', 'normal')
                if speed == 'fast': setattr(self, f'steps_per_phase{r_id}', 30)
                elif speed == 'slow': setattr(self, f'steps_per_phase{r_id}', 90)
                else: setattr(self, f'steps_per_phase{r_id}', 60)
                
                setattr(self, f'hover_height{r_id}', float(cmd.get('approach_height', 0.1)))
                self._set_state(r_id, 'INIT')

            elif action == 'place':
                setattr(self, f'target_x{r_id}', cmd.get('x', 0.0))
                setattr(self, f'target_y{r_id}', cmd.get('y', 0.0))
                
                # Dynamic Hyperparameters
                speed = cmd.get('speed', 'normal')
                if speed == 'fast': setattr(self, f'steps_per_phase{r_id}', 30)
                elif speed == 'slow': setattr(self, f'steps_per_phase{r_id}', 90)
                else: setattr(self, f'steps_per_phase{r_id}', 60)
                
                setattr(self, f'hover_height{r_id}', float(cmd.get('approach_height', 0.1)))
                curr_state = getattr(self, f'state{r_id}')
                if curr_state == 'WAITING_FOR_PLACE_CMD':
                    self._set_state(r_id, 'WAIT_FOR_CENTER')
                else:
                    self._publish_result(False, f"Robot {r_id} is in state {curr_state}, not ready to place.", f"FR3_{r_id}")

            elif action == 'go_home':
                self._send_home_cmd(r_id)
                self._set_state(r_id, 'FINISHED')
                self._publish_result(True, f"Robot {r_id} sent home.", f"FR3_{r_id}")

            elif action == 'verify_tower':
                # Send all robots home for clear view
                for i in [1, 2, 3]:
                    self._send_home_cmd(i)
                    self._set_state(i, 'FINISHED')
                self._publish_result(True, "Robots moved out of the way.", "global")

            else:
                self._publish_result(False, f"Unknown action: {action}", f"FR3_{r_id}" if r_id != 'global' else "global")

        except Exception as e:
            self._publish_result(False, f"Action parsing failed: {e}")

    def _publish_result(self, success, message, robot_id="global"):
        msg = String()
        msg.data = json.dumps({"success": success, "message": message, "robot_id": str(robot_id)})
        self.result_pub.publish(msg)

    def _resolve_block_name(self, label):
        l = label.lower()
        if 'red' in l or 'block1' in l: return 'Block1'
        elif 'green' in l or 'block2' in l: return 'Block2'
        elif 'blue' in l or 'block3' in l: return 'Block3'
        elif 'yellow' in l or 'block4' in l: return 'Block4'
        elif 'magenta' in l or 'block5' in l: return 'Block5'
        elif 'cyan' in l or 'block6' in l: return 'Block6'
        elif 'orange' in l or 'block7' in l: return 'Block7'
        elif 'purple' in l or 'block8' in l: return 'Block8'
        elif 'lime' in l or 'block9' in l: return 'Block9'
        return None

    # Coordinate Transforms & Poses

    def get_robot_base_frame(self, robot_id):
        if robot_id == 1: return 'fr3_link0'
        elif robot_id == 2: return 'FR3_2_fr3_link0'
        else: return 'FR3_3_fr3_link0'

    def get_target_block_name(self, robot_id):
        if self.mode == 'gemini':
            return getattr(self, f'active_target{robot_id}')
        else:
            # Rule-based sequence (3 blocks per robot):
            # Robot 1: Block1 (Red Cube), Block2 (Green Cyl), Block3 (Blue Cube)
            # Robot 2: Block4 (Yellow Cyl), Block5 (Magenta Cube), Block6 (Cyan Cyl)
            # Robot 3: Block7 (Orange Cube), Block8 (Purple Cyl), Block9 (Lime Cube)
            if robot_id == 1:
                return f"Block{self.block_index1 + 1}"
            elif robot_id == 2:
                return f"Block{self.block_index2 + 4}"
            else:
                return f"Block{self.block_index3 + 7}"

    def get_block_local_pose(self, robot_id):
        """Retrieve block position and optimal grasp quaternion in robot base frame."""
        name = self.get_target_block_name(robot_id)
        if not name:
            return None, None
        frame = self.get_robot_base_frame(robot_id)
        try:
            trans = self.tf_buffer.lookup_transform(frame, name, rclpy.time.Time(), timeout=Duration(seconds=0.05))
            p = trans.transform.translation
            q = trans.transform.rotation
            
            # Block yaw in base frame
            block_yaw = np.arctan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            arm_yaw = np.arctan2(p.y, p.x)
            
            # Optimal symmetry-aware downward quaternion
            target_quat = kinematics.compute_symmetric_grasp_quat(block_yaw, arm_yaw)
            return np.array([p.x, p.y, p.z]), target_quat
        except Exception as e:
            self.get_logger().error(f"TF lookup failed for {name} to {frame}: {e}")
            return None, None

    def get_place_local_pose(self, robot_id):
        """Retrieve target tower position and optimal place quaternion in robot base frame."""
        frame = self.get_robot_base_frame(robot_id)
        active_block = self.get_target_block_name(robot_id)
        
        target_x = getattr(self, f'target_x{robot_id}', 0.0)
        target_y = getattr(self, f'target_y{robot_id}', 0.0)
        
        try:
            trans = self.tf_buffer.lookup_transform(frame, 'world', rclpy.time.Time(), timeout=Duration(seconds=0.05))
            
            # Dynamically check TF frames for already placed blocks at this target X,Y
            tf_blocks_on_tower = 0
            max_block_z = None
            
            for i in range(1, 10):
                block_name = f"Block{i}"
                if block_name == active_block:
                    continue  # Do not count the block currently in the robot's gripper
                try:
                    b_trans = self.tf_buffer.lookup_transform('world', block_name, rclpy.time.Time(), timeout=Duration(seconds=0.01))
                    bx = b_trans.transform.translation.x
                    by = b_trans.transform.translation.y
                    bz = b_trans.transform.translation.z
                    dist = np.hypot(bx - target_x, by - target_y)
                    if dist < 0.045 and bz >= 0.28:  # 0.045m threshold detects vertically stacked blocks
                        tf_blocks_on_tower += 1
                        if max_block_z is None or bz > max_block_z:
                            max_block_z = bz
                except Exception:
                    pass
            
            if tf_blocks_on_tower > 0 and max_block_z is not None:
                target_z_world = max_block_z + self.block_height + 0.005
            else:
                target_z_world = 0.335  # Base table height + block center + clearance
            
            p_world = np.array([target_x, target_y, target_z_world])
            
            # Transform point from world to robot base frame
            p_rot = kinematics.quat_to_rot_matrix([
                trans.transform.rotation.w,
                trans.transform.rotation.x,
                trans.transform.rotation.y,
                trans.transform.rotation.z
            ])
            p_trans = np.array([
                trans.transform.translation.x,
                trans.transform.translation.y,
                trans.transform.translation.z
            ])
            p_local = p_rot @ p_world + p_trans
            
            # World X-axis yaw in robot base frame
            q = trans.transform.rotation
            world_yaw = np.arctan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            arm_yaw = np.arctan2(p_local[1], p_local[0])
            
            target_quat = kinematics.compute_symmetric_grasp_quat(world_yaw, arm_yaw)
            return p_local, target_quat
        except Exception as e:
            self.get_logger().warn(f"get_place_local_pose failed: {e}")
            return None, None

    # Phase Initialization & Command Helpers

    def _make_tuck_config(self, j1_angle):
        return [j1_angle] + list(self.q_tuck_body)

    def _compute_j1_for_target(self, robot_id, target_pos_local):
        # Using pure arctan2 to prevent Joint 1 limit violations ([-2.89, 2.89])
        return np.arctan2(target_pos_local[1], target_pos_local[0])

    def _initialize_joint_phase(self, robot_id, end_q, end_gripper):
        q_current = getattr(self, f'q_current{robot_id}')
        setattr(self, f'start_q{robot_id}', np.array(q_current))
        setattr(self, f'end_q{robot_id}', np.array(end_q))
        start_grip = getattr(self, f'end_gripper{robot_id}')
        setattr(self, f'start_gripper{robot_id}', start_grip)
        setattr(self, f'end_gripper{robot_id}', end_gripper)
        setattr(self, f'step_counter{robot_id}', 0)

    def _initialize_phase(self, robot_id, end_pos, end_gripper, target_quat=[0.0, 1.0, 0.0, 0.0]):
        """Capture starting waypoint and set target for the new trajectory phase."""
        if robot_id == 1:
            self.start_pos1 = kinematics.forward_kinematics(self.q_current1)[:3, 3]
            self.end_pos1 = np.array(end_pos, dtype=float)
            self.start_quat1 = list(self.end_quat1)
            self.end_quat1 = list(target_quat)
            self.start_gripper1 = self.end_gripper1
            self.end_gripper1 = end_gripper
            self.start_q1 = np.array(self.q_current1)
            q_sol, _ = kinematics.inverse_kinematics(self.end_pos1, self.end_quat1, self.start_q1)
            self.end_q1 = np.array(q_sol)
            self.step_counter1 = 0
        elif robot_id == 2:
            self.start_pos2 = kinematics.forward_kinematics(self.q_current2)[:3, 3]
            self.end_pos2 = np.array(end_pos, dtype=float)
            self.start_quat2 = list(self.end_quat2)
            self.end_quat2 = list(target_quat)
            self.start_gripper2 = self.end_gripper2
            self.end_gripper2 = end_gripper
            self.start_q2 = np.array(self.q_current2)
            q_sol, _ = kinematics.inverse_kinematics(self.end_pos2, self.end_quat2, self.start_q2)
            self.end_q2 = np.array(q_sol)
            self.step_counter2 = 0
        else:
            self.start_pos3 = kinematics.forward_kinematics(self.q_current3)[:3, 3]
            self.end_pos3 = np.array(end_pos, dtype=float)
            self.start_quat3 = list(self.end_quat3)
            self.end_quat3 = list(target_quat)
            self.start_gripper3 = self.end_gripper3
            self.end_gripper3 = end_gripper
            self.start_q3 = np.array(self.q_current3)
            q_sol, _ = kinematics.inverse_kinematics(self.end_pos3, self.end_quat3, self.start_q3)
            self.end_q3 = np.array(q_sol)
            self.step_counter3 = 0

    def _send_home_cmd(self, robot_id):
        """Command a robot to hold its retracted home configuration."""
        cmd = JointState()
        cmd.header.stamp = self.get_clock().now().to_msg()
        if robot_id == 1:
            cmd.name = self.joint_names_fr3
            cmd.position = self.q_home_fr3 + [self.gripper_open, self.gripper_open]
            self.cmd_pub1.publish(cmd)
        elif robot_id == 2:
            cmd.name = self.joint_names_fr3
            cmd.position = self.q_home_fr3 + [self.gripper_open, self.gripper_open]
            self.cmd_pub2.publish(cmd)
        elif robot_id == 3:
            cmd.name = self.joint_names_fr3
            cmd.position = self.q_home_fr3 + [self.gripper_open, self.gripper_open]
            self.cmd_pub3.publish(cmd)

    def _set_state(self, robot_id, state):
        setattr(self, f'state{robot_id}', state)

    # 50 Hz Control Loop & State Machine

    def _publish_metrics(self):
        """Publish structured robot metrics at 2 Hz for the GUI dashboard."""
        now = time.monotonic()
        robots_data = {}
        for r_id in [1, 2, 3]:
            state = getattr(self, f'state{r_id}')
            is_busy = state not in ('INIT', 'FINISHED', 'WAITING_FOR_PLACE_CMD', 'WAIT_FOR_CENTER')
            
            # Accumulate time since last transition
            dt = now - self._robot_last_transition[r_id]
            if self._robot_was_busy[r_id]:
                self._robot_busy_time[r_id] += dt
            else:
                self._robot_idle_time[r_id] += dt
            self._robot_last_transition[r_id] = now
            self._robot_was_busy[r_id] = is_busy
            
            total = self._robot_busy_time[r_id] + self._robot_idle_time[r_id]
            busy_pct = (self._robot_busy_time[r_id] / total * 100.0) if total > 0 else 0.0
            idle_pct = 100.0 - busy_pct
            
            # Determine simplified state category for the GUI
            if state in ('ROTATE_TO_PICK', 'HOVER_PICK', 'DESCEND_PICK', 'GRASP', 'LIFT'):
                gui_phase = 'PICKING'
            elif state in ('TUCK_AFTER_PICK', 'ROTATE_TO_PLACE', 'HOVER_PLACE', 'DESCEND_PLACE', 'RELEASE', 'RETRACT', 'TUCK_AFTER_PLACE'):
                gui_phase = 'PLACING'
            elif state == 'RETURN_HOME':
                gui_phase = 'HOMING'
            elif state in ('WAITING_FOR_PLACE_CMD', 'WAIT_FOR_CENTER'):
                gui_phase = 'QUEUED'
            elif state == 'FINISHED':
                gui_phase = 'IDLE'
            else:
                gui_phase = 'INIT'
            
            action = getattr(self, f'gemini_action{r_id}', None) or ''
            target = getattr(self, f'active_target{r_id}', None) or ''
            
            robots_data[f'FR3_{r_id}'] = {
                'state': state,
                'phase': gui_phase,
                'action': action,
                'target': target,
                'busy_pct': round(busy_pct, 1),
                'idle_pct': round(idle_pct, 1),
                'tasks_completed': self._tasks_completed[r_id],
                'tasks_failed': self._tasks_failed[r_id],
            }
        
        msg = String()
        msg.data = json.dumps({
            'timestamp': now - self._metrics_start_time,
            'robots': robots_data,
            'tower_height': self.tower_height,
            'center_occupied_by': f'FR3_{self.center_occupied_by}' if self.center_occupied_by else None,
        })
        self.metrics_pub.publish(msg)

    def _timer_callback(self):
        for r_id in [1, 2, 3]:
            self._process_robot(r_id)

    def _process_robot(self, robot_id):
        # Verify joint states are being received
        if robot_id == 1 and self.current_joints1 is None: return
        if robot_id == 2 and self.current_joints2 is None: return
        if robot_id == 3 and self.current_joints3 is None: return

        state = getattr(self, f'state{robot_id}')
        step_counter = getattr(self, f'step_counter{robot_id}')
        q_current = getattr(self, f'q_current{robot_id}')
        start_pos = getattr(self, f'start_pos{robot_id}')
        end_pos = getattr(self, f'end_pos{robot_id}')
        start_quat = getattr(self, f'start_quat{robot_id}')
        end_quat = getattr(self, f'end_quat{robot_id}')
        start_gripper = getattr(self, f'start_gripper{robot_id}')
        end_gripper = getattr(self, f'end_gripper{robot_id}')

        cmd_pub = self.cmd_pub1 if robot_id == 1 else (self.cmd_pub2 if robot_id == 2 else self.cmd_pub3)

        # State Machine
        if state == 'INIT':
            block_pos, block_quat = self.get_block_local_pose(robot_id)
            if block_pos is None:
                return
            j1_angle = self._compute_j1_for_target(robot_id, block_pos)
            end_q = self._make_tuck_config(j1_angle)
            self._initialize_joint_phase(robot_id, end_q, self.gripper_open)
            self._set_state(robot_id, 'ROTATE_TO_PICK')

        elif state == 'WAIT_FOR_CENTER':
            if self.center_occupied_by is None or self.center_occupied_by == robot_id:
                self.center_occupied_by = robot_id
                q_current = getattr(self, f'q_current{robot_id}')
                end_q = self._make_tuck_config(q_current[0])
                self._initialize_joint_phase(robot_id, end_q, self.gripper_close)
                self._set_state(robot_id, 'TUCK_AFTER_PICK')

        elif state in ['ROTATE_TO_PICK', 'HOVER_PICK', 'DESCEND_PICK', 'GRASP', 'LIFT',
                       'TUCK_AFTER_PICK', 'ROTATE_TO_PLACE', 'HOVER_PLACE', 'DESCEND_PLACE', 
                       'RELEASE', 'RETRACT', 'TUCK_AFTER_PLACE', 'RETURN_HOME']:
            step_counter += 1
            setattr(self, f'step_counter{robot_id}', step_counter)

            # Determine duration for this phase
            robot_steps = getattr(self, f'steps_per_phase{r_id}', self.steps_per_phase)
            total_steps = self.dwell_steps if state in ['GRASP', 'RELEASE'] else robot_steps
            t = min(float(step_counter) / float(total_steps), 1.0)
            
            # Minimum Jerk Quintic Polynomial (MoveIt 2 standard trajectory profile)
            t_smooth = 10 * (t ** 3) - 15 * (t ** 4) + 6 * (t ** 5)

            if state in ['ROTATE_TO_PICK', 'HOVER_PICK', 'TUCK_AFTER_PICK', 'ROTATE_TO_PLACE', 
                         'HOVER_PLACE', 'TUCK_AFTER_PLACE', 'RETURN_HOME']:
                # JOINT SPACE INTERPOLATION
                start_q = getattr(self, f'start_q{robot_id}')
                end_q = getattr(self, f'end_q{robot_id}')
                q_sol = start_q + t_smooth * (end_q - start_q)
                for i in range(7):
                    q_sol[i] = np.clip(q_sol[i], kinematics.FR3_JOINT_LIMITS[i][0], kinematics.FR3_JOINT_LIMITS[i][1])
            elif state in ['GRASP', 'RELEASE']:
                q_sol = np.array(q_current)
            else:
                # CARTESIAN SPACE INTERPOLATION
                if start_pos is not None and end_pos is not None:
                    target_pos = start_pos + t_smooth * (end_pos - start_pos)
                else:
                    target_pos = end_pos

                target_quat = kinematics.interpolate_quat(start_quat, end_quat, t_smooth)
                q_sol, success = kinematics.inverse_kinematics(target_pos, target_quat, q_current)

            grip_target = start_gripper + t_smooth * (end_gripper - start_gripper)

            # Publish joint commands
            cmd = JointState()
            cmd.header.stamp = self.get_clock().now().to_msg()
            cmd.name = self.joint_names_fr3
            cmd.position = list(q_sol) + [grip_target, grip_target]
            cmd_pub.publish(cmd)

            # Update warm-start joint cache
            if robot_id == 1:
                for i in range(7): self.q_current1[i] = q_sol[i]
            elif robot_id == 2:
                for i in range(7): self.q_current2[i] = q_sol[i]
            else:
                for i in range(7): self.q_current3[i] = q_sol[i]

            # Transition when phase completes
            if step_counter >= total_steps:
                if state == 'ROTATE_TO_PICK':
                    block_pos, block_quat = self.get_block_local_pose(robot_id)
                    if block_pos is None: return
                    hover_pos = np.array([block_pos[0], block_pos[1], block_pos[2] + self.hover_height])
                    self._initialize_phase(robot_id, hover_pos, self.gripper_open, block_quat)
                    self._set_state(robot_id, 'HOVER_PICK')

                elif state == 'HOVER_PICK':
                    block_pos, block_quat = self.get_block_local_pose(robot_id)
                    if block_pos is None: return
                    self._initialize_phase(robot_id, block_pos, self.gripper_open, block_quat)
                    self._set_state(robot_id, 'DESCEND_PICK')

                elif state == 'DESCEND_PICK':
                    # Grasp block: close gripper while holding position
                    self._initialize_phase(robot_id, end_pos, self.gripper_close, end_quat)
                    self._set_state(robot_id, 'GRASP')

                elif state == 'GRASP':
                    # Lift block vertically
                    lift_pos = np.array([end_pos[0], end_pos[1], end_pos[2] + self.hover_height])
                    self._initialize_phase(robot_id, lift_pos, self.gripper_close, end_quat)
                    self._set_state(robot_id, 'LIFT')

                elif state == 'LIFT':
                    gripper_pos = getattr(self, f'current_gripper{robot_id}')
                    pick_success = gripper_pos > 0.01  # > 1cm width means we grasped something

                    if self.mode == 'gemini' and getattr(self, f'gemini_action{robot_id}') == 'pick':
                        if pick_success:
                            self._set_state(robot_id, 'WAITING_FOR_PLACE_CMD')
                            self._publish_result(True, f"Pick completed by robot {robot_id}. Grasped object successfully.", f"FR3_{robot_id}")
                        else:
                            # It missed!
                            self._set_state(robot_id, 'FINISHED')
                            self._publish_result(False, f"Pick failed by robot {robot_id}. Gripper closed on empty space.", f"FR3_{robot_id}")
                            self._tasks_failed[robot_id] += 1
                    else:
                        if pick_success:
                            self._set_state(robot_id, 'WAITING_FOR_CENTER')
                        else:
                            self.get_logger().warn(f"Robot {robot_id} failed to grasp! Retrying...")
                            self._set_state(robot_id, 'INIT')

                elif state == 'TUCK_AFTER_PICK':
                    place_pos, _ = self.get_place_local_pose(robot_id)
                    if place_pos is None: return
                    j1_angle = self._compute_j1_for_target(robot_id, place_pos)
                    end_q = self._make_tuck_config(j1_angle)
                    self._initialize_joint_phase(robot_id, end_q, self.gripper_close)
                    self._set_state(robot_id, 'ROTATE_TO_PLACE')

                elif state == 'ROTATE_TO_PLACE':
                    place_pos, place_quat = self.get_place_local_pose(robot_id)
                    if place_pos is None: return
                    hover_h = getattr(self, f'hover_height{robot_id}', self.hover_height)
                    hover_place_pos = np.array([place_pos[0], place_pos[1], place_pos[2] + hover_h])
                    self._initialize_phase(robot_id, hover_place_pos, self.gripper_close, place_quat)
                    self._set_state(robot_id, 'HOVER_PLACE')

                elif state == 'HOVER_PLACE':
                    place_pos, place_quat = self.get_place_local_pose(robot_id)
                    if place_pos is None: return
                    self._initialize_phase(robot_id, place_pos, self.gripper_close, place_quat)
                    self._set_state(robot_id, 'DESCEND_PLACE')

                elif state == 'DESCEND_PLACE':
                    # Release block: open gripper
                    self._initialize_phase(robot_id, end_pos, self.gripper_open, end_quat)
                    self._set_state(robot_id, 'RELEASE')

                elif state == 'RELEASE':
                    # Retract vertically
                    retract_pos = np.array([end_pos[0], end_pos[1], end_pos[2] + self.hover_height])
                    self._initialize_phase(robot_id, retract_pos, self.gripper_open, end_quat)
                    self._set_state(robot_id, 'RETRACT')

                elif state == 'RETRACT':
                    self.tower_height += 1
                    self.get_logger().info(f"Tower height incremented to: {self.tower_height}")
                    q_current = getattr(self, f'q_current{robot_id}')
                    end_q = self._make_tuck_config(q_current[0])
                    self._initialize_joint_phase(robot_id, end_q, self.gripper_open)
                    self._set_state(robot_id, 'TUCK_AFTER_PLACE')

                elif state == 'TUCK_AFTER_PLACE':
                    self._initialize_joint_phase(robot_id, self.q_home_fr3, self.gripper_open)
                    self._set_state(robot_id, 'RETURN_HOME')

                elif state == 'RETURN_HOME':
                    if self.center_occupied_by == robot_id:
                        self.center_occupied_by = None

                    if self.mode == 'gemini' and getattr(self, f'gemini_action{robot_id}') == 'place':
                        self._set_state(robot_id, 'FINISHED')
                        self._publish_result(True, f"Place completed by robot {robot_id}. Tower height is now {self.tower_height}.", f"FR3_{robot_id}")
                        self._tasks_completed[robot_id] += 1
                    else:
                        # Advance block index for current robot
                        max_blocks_per_robot = 3
                        curr_idx = getattr(self, f'block_index{robot_id}')
                        if curr_idx < max_blocks_per_robot - 1:
                            setattr(self, f'block_index{robot_id}', curr_idx + 1)
                            self._set_state(robot_id, 'INIT')
                        else:
                            self._set_state(robot_id, 'FINISHED')
                            self.get_logger().info(f"[SEQUENCER] Robot {robot_id} finished all its tasks.")


def main(args=None):
    rclpy.init(args=args)
    node = MultiRobotController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

