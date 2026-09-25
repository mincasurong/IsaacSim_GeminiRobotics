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


class ConveyorDualController(Node):
    """Unified Controller and Motion Planner for FR3_1 and FR3_2."""

    def __init__(self):
        super().__init__('conveyor_dual_controller')

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
        self.status_pub = self.create_publisher(String, '/multi_robot/status', 10)
        self.result_pub = self.create_publisher(String, '/gemini/action_result', 10)
        self.metrics_pub = self.create_publisher(String, '/multi_robot/robot_metrics', 10)

        # Subscribers
        self.state_sub1 = self.create_subscription(JointState, '/fr3_1/joint_states', self._state_cb1, 10)
        self.state_sub2 = self.create_subscription(JointState, '/fr3_2/joint_states', self._state_cb2, 10)
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
        
        self.current_gripper1 = 0.0
        self.current_gripper2 = 0.0

        self.q_current1 = list(self.q_home_fr3)
        self.q_current2 = list(self.q_home_fr3)
        
        self.rotation_dir1 = 'shortest'
        self.rotation_dir2 = 'shortest'

        self.state1 = 'INIT'
        self.state2 = 'INIT'

        self.block_index1 = 0
        self.block_index2 = 0

        self.step_counter1 = 0
        self.step_counter2 = 0

        self.start_pos1 = None; self.end_pos1 = None
        self.start_pos2 = None; self.end_pos2 = None

        self.start_quat1 = [0.0, 1.0, 0.0, 0.0]; self.end_quat1 = [0.0, 1.0, 0.0, 0.0]
        self.start_quat2 = [0.0, 1.0, 0.0, 0.0]; self.end_quat2 = [0.0, 1.0, 0.0, 0.0]

        self.start_q1 = list(self.q_home_fr3); self.end_q1 = list(self.q_home_fr3)
        self.start_q2 = list(self.q_home_fr3); self.end_q2 = list(self.q_home_fr3)

        self.start_gripper1 = self.gripper_open; self.end_gripper1 = self.gripper_open
        self.start_gripper2 = self.gripper_open; self.end_gripper2 = self.gripper_open

        self.tower_height = 0
        self.active_robot_id = 1
        
        self.active_target1 = None
        self.active_target2 = None
        
        self.gemini_action1 = None
        self.gemini_action2 = None
        self.center_occupied_by = None

        # Metrics & Utilization Tracking
        self._metrics_start_time = time.monotonic()
        self._robot_busy_time = {1: 0.0, 2: 0.0}
        self._robot_idle_time = {1: 0.0, 2: 0.0}
        self._robot_last_transition = {1: time.monotonic(), 2: time.monotonic()}
        self._robot_was_busy = {1: False, 2: False}
        self._tasks_completed = {1: 0, 2: 0}
        self._tasks_failed = {1: 0, 2: 0}
        self._action_start_time = {1: None, 2: None, 'global': None}

        # 50 Hz Control Loop Timer
        self.timer = self.create_timer(0.02, self._timer_callback)
        self.metrics_timer = self.create_timer(0.5, self._publish_metrics)

        self.get_logger().info(
            f"ConveyorDualController initialized. Mode: [{self.mode.upper()}]. "
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
        self.block_index1 = 0
        self.block_index2 = 0
        self.step_counter1 = 0
        self.step_counter2 = 0
        self.q_current1 = list(self.q_home_fr3)
        self.q_current2 = list(self.q_home_fr3)
        self.tower_height = 0
        self.active_robot_id = 1
        
        self.active_target1 = None
        self.active_target2 = None
        
        self.gemini_action1 = None
        self.gemini_action2 = None
        
        self.center_occupied_by = None
        
        self._metrics_start_time = time.monotonic()
        self._robot_busy_time = {1: 0.0, 2: 0.0}
        self._robot_idle_time = {1: 0.0, 2: 0.0}
        self._robot_last_transition = {1: time.monotonic(), 2: time.monotonic()}
        self._robot_was_busy = {1: False, 2: False}
        self._tasks_completed = {1: 0, 2: 0}
        self._tasks_failed = {1: 0, 2: 0}
        self._action_start_time = {1: None, 2: None, 'global': None}

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
                pass
                self._publish_result(False, f"Unknown robot identifier: {robot_str}")
                return

            self._action_start_time[r_id] = time.monotonic()

            if r_id != 'global':
                setattr(self, f'gemini_action{r_id}', action)

            if action == 'pick':
                target_label = cmd.get('target', '')
                block_name = self._resolve_block_name(target_label)
                if not block_name:
                    self._publish_result(False, f"Could not map target '{target_label}' to a block prim.", f"FR3_{r_id}")
                    return
                setattr(self, f'active_target{r_id}', block_name)
                
                # Dynamic Hyperparameters (Optimized for High Agility & Speed)
                speed = cmd.get('speed', 'fast')
                if speed == 'fast': setattr(self, f'steps_per_phase{r_id}', 20)
                elif speed == 'slow': setattr(self, f'steps_per_phase{r_id}', 70)
                else: setattr(self, f'steps_per_phase{r_id}', 40)
                
                setattr(self, f'hover_height{r_id}', float(cmd.get('approach_height', 0.1)))
                self._set_state(r_id, 'INIT')

            elif action == 'place':
                setattr(self, f'target_x{r_id}', cmd.get('x', 0.0))
                setattr(self, f'target_y{r_id}', cmd.get('y', 0.0))
                
                # Dynamic Hyperparameters (Optimized for High Agility & Speed)
                speed = cmd.get('speed', 'fast')
                if speed == 'fast': setattr(self, f'steps_per_phase{r_id}', 20)
                elif speed == 'slow': setattr(self, f'steps_per_phase{r_id}', 70)
                else: setattr(self, f'steps_per_phase{r_id}', 40)
                
                setattr(self, f'hover_height{r_id}', float(cmd.get('approach_height', 0.1)))
                curr_state = getattr(self, f'state{r_id}')
                if curr_state == 'WAITING_FOR_PLACE_CMD':
                    self._set_state(r_id, 'WAIT_FOR_CENTER')
                else:
                    pass
                    self._publish_result(False, f"Robot {r_id} is in state {curr_state}, not ready to place.", f"FR3_{r_id}")

            elif action == 'go_home':
                if self.center_occupied_by == r_id:
                    self.center_occupied_by = None
                self._send_home_cmd(r_id)
                self._set_state(r_id, 'FINISHED')
                self._publish_result(True, f"Robot {r_id} sent home.", f"FR3_{r_id}")

            elif action == 'verify_tower':
                # Send all robots home for clear view
                self.center_occupied_by = None
                for i in [1, 2, 3]:
                    self._send_home_cmd(i)
                    self._set_state(i, 'FINISHED')
                self._publish_result(True, "Robots moved out of the way.", "global")

            else:
                pass
                self._publish_result(False, f"Unknown action: {action}", f"FR3_{r_id}" if r_id != 'global' else "global")

        except Exception as e:
            self._publish_result(False, f"Action parsing failed: {e}")

    def _publish_result(self, success, message, robot_id="global"):
        r_key = robot_id
        if isinstance(robot_id, str):
            if "1" in robot_id: r_key = 1
            elif "2" in robot_id: r_key = 2
            elif "3" in robot_id: r_key = 3
            else: r_key = "global"

        start_t = self._action_start_time.get(r_key)
        elapsed_sec = round(time.monotonic() - start_t, 4) if start_t is not None else 0.0

        msg = String()
        payload = {
            "success": bool(success),
            "message": str(message),
            "robot_id": str(robot_id),
            "elapsed_sec": elapsed_sec,
            "wall_timestamp": time.time()
        }
        msg.data = json.dumps(payload)
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
            pass
            # Rule-based sequence (3 blocks per robot):
            # Robot 1: Block1 (Red Cube), Block2 (Green Cyl), Block3 (Blue Cube)
            # Robot 2: Block4 (Yellow Cyl), Block5 (Magenta Cube), Block6 (Cyan Cyl)
            # Robot 3: Block7 (Orange Cube), Block8 (Purple Cyl), Block9 (Lime Cube)
            if robot_id == 1:
                return f"Block{self.block_index1 + 1}"
            elif robot_id == 2:
                return f"Block{self.block_index2 + 4}"
            else:
                pass

    def get_block_local_pose(self, robot_id):
        """Retrieve block position and optimal grasp quaternion in robot base frame."""
        name = self.get_target_block_name(robot_id)
        if not name:
            return None, None
        frame = self.get_robot_base_frame(robot_id)
        try:
            trans = self.tf_buffer.lookup_transform(frame, name, rclpy.time.Time())
            p = trans.transform.translation
            q = trans.transform.rotation
            
            # Block yaw in base frame
            block_yaw = np.arctan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            
            # If it's a LongBar, we add a lateral offset so the robots grab the ends
            if name == 'LongBar':
                offset_dist = -0.3 if robot_id == 1 else 0.3
                p.x += offset_dist * np.cos(block_yaw)
                p.y += offset_dist * np.sin(block_yaw)

            arm_yaw = np.arctan2(p.y, p.x)
            
            # Optimal symmetry-aware downward quaternion
            target_quat = kinematics.compute_symmetric_grasp_quat(block_yaw, arm_yaw)
            
            if name == 'LongBar':
                target_quat = kinematics.compute_symmetric_grasp_quat(block_yaw + np.pi/2, arm_yaw)
                
            return np.array([p.x, p.y, p.z]), target_quat
        except Exception as e:
            self.get_logger().error(f"TF lookup failed for {name} to {frame}: {e}", throttle_duration_sec=1.0)
            return None, None
        frame = self.get_robot_base_frame(robot_id)
        try:
            trans = self.tf_buffer.lookup_transform(frame, name, rclpy.time.Time())
            p = trans.transform.translation
            q = trans.transform.rotation
            
            # Block yaw in base frame
            block_yaw = np.arctan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            arm_yaw = np.arctan2(p.y, p.x)
            
            # Optimal symmetry-aware downward quaternion
            target_quat = kinematics.compute_symmetric_grasp_quat(block_yaw, arm_yaw)
            return np.array([p.x, p.y, p.z]), target_quat
        except Exception as e:
            self.get_logger().error(f"TF lookup failed for {name} to {frame}: {e}", throttle_duration_sec=1.0)
            return None, None

    def get_place_local_pose(self, robot_id):
        """Retrieve target tower position and optimal place quaternion in robot base frame."""
        frame = self.get_robot_base_frame(robot_id)
        active_block = self.get_target_block_name(robot_id)
        
        target_x = getattr(self, f'target_x{robot_id}', 0.0)
        target_y = getattr(self, f'target_y{robot_id}', 0.0)
        
        try:
            trans = self.tf_buffer.lookup_transform(frame, 'world', rclpy.time.Time())
            
            # Dynamically check TF frames for already placed blocks at this target X,Y
            tf_blocks_on_tower = 0
            max_block_z = None
            
            for i in range(1, 10):
                block_name = f"Block{i}"
                if block_name == active_block:
                    continue  # Do not count the block currently in the robot's gripper
                try:
                    b_trans = self.tf_buffer.lookup_transform('world', block_name, rclpy.time.Time())
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
                pass
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
            self.get_logger().warn(f"get_place_local_pose failed: {e}", throttle_duration_sec=1.0)
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
            pass

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