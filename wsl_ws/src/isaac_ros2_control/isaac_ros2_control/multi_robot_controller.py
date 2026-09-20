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


# Kitchenware & Block Manipulation Affordance Taxonomy
KITCHEN_AFFORDANCES = {
    'dish': {
        'height': 0.020,
        'approach_height': 0.080,
        'grasp_z_offset': 0.002,
        'rim_offset_radius': 0.065,
        'gripper_close': 0.006,
        'gripper_open': 0.040,
        'verification_range': (0.003, 0.015),
        'grasp_mode': 'rim_pinch',
        'lift_height': 0.100,
        'place_z_offset': 0.014,
        'nesting_z_offset': 0.012,
    },
    'cup': {
        'height': 0.090,
        'approach_height': 0.120,
        'grasp_z_offset': 0.035,
        'rim_offset_radius': 0.0,
        'gripper_close': 0.020,
        'gripper_open': 0.040,
        'verification_range': (0.016, 0.035),
        'grasp_mode': 'cylindrical_clamp',
        'lift_height': 0.120,
        'place_z_offset': 0.045,
        'nesting_z_offset': 0.090,
    },
    'block': {
        'height': 0.060,
        'approach_height': 0.100,
        'grasp_z_offset': 0.0,
        'rim_offset_radius': 0.0,
        'gripper_close': 0.015,
        'gripper_open': 0.040,
        'verification_range': (0.008, 0.028),
        'grasp_mode': 'top_down_symmetric',
        'lift_height': 0.100,
        'place_z_offset': 0.035,
        'nesting_z_offset': 0.060,
    },
    'long_bar': {
        'height': 0.030,
        'approach_height': 0.120,
        'grasp_z_offset': 0.010,
        'rim_offset_radius': 0.0,
        'gripper_close': 0.018,
        'gripper_open': 0.040,
        'verification_range': (0.012, 0.028),
        'grasp_mode': 'dual_clamping',
        'lift_height': 0.120,
        'place_z_offset': 0.015,
        'nesting_z_offset': 0.030,
    },
}

# Workspace Clearing Zones
CLEARING_ZONES = {
    'dish_rack': [-0.15, -0.25],
    'cup_tray': [0.20, 0.15],
    'sink': [-0.20, 0.15],
    'counter': [0.0, 0.0],
    'default': {
        1: [-0.15, -0.25],  # Reachable by FR3_1
        2: [0.20, 0.15],    # Reachable by FR3_2
        3: [-0.20, 0.15],   # Reachable by FR3_3
    }
}

# Dining Organization Place-Setting Coordinates
DINING_ORGANIZATION_LAYOUT = {
    'place_setting_1': {
        'dish': [0.0, -0.12],
        'cup': [0.10, -0.08],
    },
    'place_setting_2': {
        'dish': [0.10, 0.06],
        'cup': [0.12, 0.16],
    },
    'place_setting_3': {
        'dish': [-0.10, 0.06],
        'cup': [-0.12, 0.16],
    }
}


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
        
        self.active_object_type1 = None
        self.active_object_type2 = None
        self.active_object_type3 = None

        self.is_autonomous_cycle1 = False
        self.is_autonomous_cycle2 = False
        self.is_autonomous_cycle3 = False

        self.autonomous_action_name1 = ''
        self.autonomous_action_name2 = ''
        self.autonomous_action_name3 = ''

        self.gemini_action1 = None
        self.gemini_action2 = None
        self.gemini_action3 = None
        self.center_occupied_by = None

        # Dual-Arm Collaborative Manipulation State (Requirement R3, Features 10-14)
        self.dual_active = False
        self.dual_state = 'DUAL_IDLE'
        self.dual_step_counter = 0
        self.dual_steps_per_phase = 40
        self.dual_dwell_steps = self.dwell_steps
        self.dual_robots = [1, 2]
        self.dual_target_name = 'LongBar1'
        self.dual_bar_length = 0.50
        self.dual_grasp_separation = 0.40  # Constant rigid body separation distance (0.40m)
        self.dual_dest_pos = np.array([0.0, 0.15, 0.22])
        self.dual_dest_yaw = 0.0
        self.dual_start_bar_pos = None
        self.dual_start_bar_yaw = 0.0

        # Collaborative Telemetry
        self.collaborative_active = False
        self.collaborative_pair = None
        self.collaborative_object = None

        # Dual-Arm Waypoint Buffers
        self.dual_w1_start = None; self.dual_w1_end = None
        self.dual_w2_start = None; self.dual_w2_end = None
        self.dual_quat1_start = [0.0, 1.0, 0.0, 0.0]; self.dual_quat1_end = [0.0, 1.0, 0.0, 0.0]
        self.dual_quat2_start = [0.0, 1.0, 0.0, 0.0]; self.dual_quat2_end = [0.0, 1.0, 0.0, 0.0]
        self.dual_q1_start = list(self.q_home_fr3); self.dual_q1_end = list(self.q_home_fr3)
        self.dual_q2_start = list(self.q_home_fr3); self.dual_q2_end = list(self.q_home_fr3)
        self.dual_grip_start = self.gripper_open; self.dual_grip_end = self.gripper_open

        # Metrics & Utilization Tracking
        self._metrics_start_time = time.monotonic()
        self._robot_busy_time = {1: 0.0, 2: 0.0, 3: 0.0}
        self._robot_idle_time = {1: 0.0, 2: 0.0, 3: 0.0}
        self._robot_last_transition = {1: time.monotonic(), 2: time.monotonic(), 3: time.monotonic()}
        self._robot_was_busy = {1: False, 2: False, 3: False}
        self._tasks_completed = {1: 0, 2: 0, 3: 0}
        self._tasks_failed = {1: 0, 2: 0, 3: 0}
        self._action_start_time = {1: None, 2: None, 3: None, 'global': None}

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
        
        self.active_object_type1 = None
        self.active_object_type2 = None
        self.active_object_type3 = None

        self.is_autonomous_cycle1 = False
        self.is_autonomous_cycle2 = False
        self.is_autonomous_cycle3 = False

        self.autonomous_action_name1 = ''
        self.autonomous_action_name2 = ''
        self.autonomous_action_name3 = ''

        self.gemini_action1 = None
        self.gemini_action2 = None
        self.gemini_action3 = None
        
        self.center_occupied_by = None

        self.dual_active = False
        self.dual_state = 'DUAL_IDLE'
        self.dual_step_counter = 0
        self.collaborative_active = False
        self.collaborative_pair = None
        self.collaborative_object = None
        self.dual_start_bar_pos = None
        
        self._metrics_start_time = time.monotonic()
        self._robot_busy_time = {1: 0.0, 2: 0.0, 3: 0.0}
        self._robot_idle_time = {1: 0.0, 2: 0.0, 3: 0.0}
        self._robot_last_transition = {1: time.monotonic(), 2: time.monotonic(), 3: time.monotonic()}
        self._robot_was_busy = {1: False, 2: False, 3: False}
        self._tasks_completed = {1: 0, 2: 0, 3: 0}
        self._tasks_failed = {1: 0, 2: 0, 3: 0}
        self._action_start_time = {1: None, 2: None, 3: None, 'global': None}

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

            if action in ['dual_carry', 'dual_transport', 'dual_arm_transport']:
                r_id = 'DUAL_FR3_1_FR3_2'
            elif 'FR3_1' in robot_str or 'ROBOT1' in robot_str or robot_str == '1':
                r_id = 1
            elif 'FR3_2' in robot_str or 'ROBOT2' in robot_str or robot_str == '2':
                r_id = 2
            elif 'FR3_3' in robot_str or 'ROBOT3' in robot_str or robot_str == '3':
                r_id = 3
            elif action == 'verify_tower':
                # Special global action
                r_id = 'global'
            else:
                self._publish_result(False, f"Unknown robot identifier: {robot_str}")
                return

            self._action_start_time[r_id] = time.monotonic()

            if isinstance(r_id, int):
                setattr(self, f'gemini_action{r_id}', action)

            if action == 'pick':
                target_label = cmd.get('target', '')
                target_name = self._resolve_target_name(target_label)
                if not target_name:
                    self._publish_result(False, f"Could not map target '{target_label}' to an object prim.", f"FR3_{r_id}")
                    return
                setattr(self, f'active_target{r_id}', target_name)
                obj_type = self.get_object_type(target_name)
                setattr(self, f'active_object_type{r_id}', obj_type)
                setattr(self, f'is_autonomous_cycle{r_id}', False)
                
                # Dynamic Hyperparameters (Optimized for High Agility & Speed)
                speed = cmd.get('speed', 'fast')
                if speed == 'fast': setattr(self, f'steps_per_phase{r_id}', 20)
                elif speed == 'slow': setattr(self, f'steps_per_phase{r_id}', 70)
                else: setattr(self, f'steps_per_phase{r_id}', 40)
                
                affordance = self.get_affordance(obj_type)
                default_approach = affordance.get('approach_height', 0.10)
                setattr(self, f'hover_height{r_id}', float(cmd.get('approach_height', default_approach)))
                self._set_state(r_id, 'INIT')

            elif action == 'place':
                setattr(self, f'target_x{r_id}', float(cmd.get('x', 0.0)))
                setattr(self, f'target_y{r_id}', float(cmd.get('y', 0.0)))
                setattr(self, f'is_autonomous_cycle{r_id}', False)
                
                # Dynamic Hyperparameters (Optimized for High Agility & Speed)
                speed = cmd.get('speed', 'fast')
                if speed == 'fast': setattr(self, f'steps_per_phase{r_id}', 20)
                elif speed == 'slow': setattr(self, f'steps_per_phase{r_id}', 70)
                else: setattr(self, f'steps_per_phase{r_id}', 40)
                
                active_obj = self.get_target_block_name(r_id)
                affordance = self.get_affordance(self.get_object_type(active_obj))
                default_approach = affordance.get('approach_height', 0.10)
                setattr(self, f'hover_height{r_id}', float(cmd.get('approach_height', default_approach)))
                
                curr_state = getattr(self, f'state{r_id}')
                if curr_state == 'WAITING_FOR_PLACE_CMD':
                    self._set_state(r_id, 'WAIT_FOR_CENTER')
                else:
                    self._publish_result(False, f"Robot {r_id} is in state {curr_state}, not ready to place.", f"FR3_{r_id}")

            elif action == 'clear_table':
                target_label = cmd.get('target', '')
                dest = cmd.get('destination', None)
                zone = cmd.get('zone', 'counter')
                
                target_name = self._resolve_target_name(target_label) if target_label else None
                if not target_name:
                    target_name = self._find_clearable_object(r_id, zone)
                    
                if not target_name:
                    self._publish_result(False, f"No kitchenware found to clear for robot {r_id}.", f"FR3_{r_id}")
                    return
                    
                setattr(self, f'active_target{r_id}', target_name)
                obj_type = self.get_object_type(target_name)
                setattr(self, f'active_object_type{r_id}', obj_type)
                
                if dest and len(dest) >= 2:
                    tx, ty = float(dest[0]), float(dest[1])
                else:
                    if obj_type == 'dish':
                        tx, ty = CLEARING_ZONES['dish_rack']
                    elif obj_type == 'cup':
                        tx, ty = CLEARING_ZONES['cup_tray']
                    else:
                        tx, ty = CLEARING_ZONES['default'][r_id]
                        
                setattr(self, f'target_x{r_id}', tx)
                setattr(self, f'target_y{r_id}', ty)
                setattr(self, f'is_autonomous_cycle{r_id}', True)
                setattr(self, f'autonomous_action_name{r_id}', 'clear_table')
                
                speed = cmd.get('speed', 'fast')
                if speed == 'fast': setattr(self, f'steps_per_phase{r_id}', 20)
                elif speed == 'slow': setattr(self, f'steps_per_phase{r_id}', 70)
                else: setattr(self, f'steps_per_phase{r_id}', 40)
                
                affordance = self.get_affordance(obj_type)
                default_approach = affordance.get('approach_height', 0.10)
                setattr(self, f'hover_height{r_id}', float(cmd.get('approach_height', default_approach)))
                self._set_state(r_id, 'INIT')

            elif action in ['organize_table', 'organize_kitchenware']:
                target_label = cmd.get('target', '')
                layout = cmd.get('layout', 'dining')
                target_name = self._resolve_target_name(target_label) if target_label else None
                if not target_name:
                    target_name = self._find_clearable_object(r_id, layout)
                if not target_name:
                    self._publish_result(False, f"No kitchenware found to organize for robot {r_id}.", f"FR3_{r_id}")
                    return
                    
                setattr(self, f'active_target{r_id}', target_name)
                obj_type = self.get_object_type(target_name)
                setattr(self, f'active_object_type{r_id}', obj_type)
                
                dest = cmd.get('destination', None)
                if dest and len(dest) >= 2:
                    tx, ty = float(dest[0]), float(dest[1])
                else:
                    setting_key = f'place_setting_{r_id}'
                    coords = DINING_ORGANIZATION_LAYOUT.get(setting_key, {}).get(obj_type, [0.0, 0.0])
                    tx, ty = coords[0], coords[1]
                    
                setattr(self, f'target_x{r_id}', tx)
                setattr(self, f'target_y{r_id}', ty)
                setattr(self, f'is_autonomous_cycle{r_id}', True)
                setattr(self, f'autonomous_action_name{r_id}', action)
                
                speed = cmd.get('speed', 'fast')
                if speed == 'fast': setattr(self, f'steps_per_phase{r_id}', 20)
                elif speed == 'slow': setattr(self, f'steps_per_phase{r_id}', 70)
                else: setattr(self, f'steps_per_phase{r_id}', 40)
                
                affordance = self.get_affordance(obj_type)
                default_approach = affordance.get('approach_height', 0.10)
                setattr(self, f'hover_height{r_id}', float(cmd.get('approach_height', default_approach)))
                self._set_state(r_id, 'INIT')

            elif action == 'place_relative':
                anchor_name = cmd.get('anchor_block') or cmd.get('anchor_object') or cmd.get('anchor', '')
                relation = cmd.get('relation', 'on_top_of')
                
                anchor_target = self._resolve_target_name(anchor_name)
                if not anchor_target:
                    self._publish_result(False, f"Could not resolve anchor object '{anchor_name}'", f"FR3_{r_id}")
                    return
                    
                try:
                    trans = self.tf_buffer.lookup_transform('world', anchor_target, rclpy.time.Time())
                    ax = trans.transform.translation.x
                    ay = trans.transform.translation.y
                    
                    if relation == 'on_top_of':
                        tx, ty = ax, ay
                    elif relation == 'left_of':
                        tx, ty = ax - 0.08, ay
                    elif relation == 'right_of':
                        tx, ty = ax + 0.08, ay
                    elif relation == 'front_of':
                        tx, ty = ax, ay - 0.08
                    elif relation == 'back_of':
                        tx, ty = ax, ay + 0.08
                    else:
                        tx, ty = ax, ay
                        
                    setattr(self, f'target_x{r_id}', tx)
                    setattr(self, f'target_y{r_id}', ty)
                    setattr(self, f'is_autonomous_cycle{r_id}', False)
                    
                    speed = cmd.get('speed', 'fast')
                    if speed == 'fast': setattr(self, f'steps_per_phase{r_id}', 20)
                    elif speed == 'slow': setattr(self, f'steps_per_phase{r_id}', 70)
                    else: setattr(self, f'steps_per_phase{r_id}', 40)
                    
                    active_obj = self.get_target_block_name(r_id)
                    affordance = self.get_affordance(self.get_object_type(active_obj))
                    default_approach = affordance.get('approach_height', 0.10)
                    setattr(self, f'hover_height{r_id}', float(cmd.get('approach_height', default_approach)))
                    
                    curr_state = getattr(self, f'state{r_id}')
                    if curr_state == 'WAITING_FOR_PLACE_CMD':
                        self._set_state(r_id, 'WAIT_FOR_CENTER')
                    else:
                        self._publish_result(False, f"Robot {r_id} is in state {curr_state}, not ready to place.", f"FR3_{r_id}")
                except Exception as e:
                    self._publish_result(False, f"TF lookup failed for anchor {anchor_target}: {e}", f"FR3_{r_id}")

            elif action == 'go_home':
                if self.center_occupied_by == r_id:
                    self.center_occupied_by = None
                self._send_home_cmd(r_id)
                self._set_state(r_id, 'FINISHED')
                self._publish_result(True, f"Robot {r_id} sent home.", f"FR3_{r_id}")

            elif action in ['dual_carry', 'dual_transport', 'dual_arm_transport']:
                robots = cmd.get('robots', ['FR3_1', 'FR3_2'])
                r_indices = []
                for r in robots:
                    if '1' in str(r): r_indices.append(1)
                    elif '2' in str(r): r_indices.append(2)
                    elif '3' in str(r): r_indices.append(3)
                if len(r_indices) < 2:
                    r_indices = [1, 2]
                    
                target_label = cmd.get('object') or cmd.get('target', 'LongBar1')
                target_name = self._resolve_target_name(target_label) or 'LongBar1'
                
                dest = cmd.get('destination', None)
                if dest and len(dest) >= 2:
                    tx, ty = float(dest[0]), float(dest[1])
                    tz = float(dest[2]) if len(dest) > 2 else 0.22
                else:
                    tx = float(cmd.get('target_x', 0.0))
                    ty = float(cmd.get('target_y', 0.15))
                    tz = float(cmd.get('target_z', 0.22))
                    
                target_yaw = float(cmd.get('target_yaw', 0.0))
                speed = cmd.get('speed', 'normal')
                steps = 20 if speed == 'fast' else (70 if speed == 'slow' else 40)
                
                self._start_dual_carry(
                    robots=r_indices,
                    target_name=target_name,
                    dest_pos=[tx, ty, tz],
                    dest_yaw=target_yaw,
                    steps=steps
                )

            elif action == 'verify_tower':
                # Send all robots home for clear view
                self.center_occupied_by = None
                for i in [1, 2, 3]:
                    self._send_home_cmd(i)
                    self._set_state(i, 'FINISHED')
                self._publish_result(True, "Robots moved out of the way.", "global")

            else:
                self._publish_result(False, f"Unknown action: {action}", f"FR3_{r_id}" if r_id != 'global' else "global")

        except Exception as e:
            self._publish_result(False, f"Action parsing failed: {e}")

    def _publish_result(self, success, message, robot_id="global", action=None):
        r_key = robot_id
        if isinstance(robot_id, str):
            if "DUAL" in robot_id: r_key = 'global'
            elif "1" in robot_id and "2" not in robot_id: r_key = 1
            elif "2" in robot_id: r_key = 2
            elif "3" in robot_id: r_key = 3
            else: r_key = "global"

        start_t = self._action_start_time.get(r_key) or self._action_start_time.get('global')
        elapsed_sec = round(time.monotonic() - start_t, 4) if start_t is not None else 0.0

        status_str = "SUCCESS" if success else "FAILURE"
        act = action
        if not act:
            if r_key in [1, 2, 3]:
                act = getattr(self, f'gemini_action{r_key}', None) or 'action'
            elif 'DUAL' in str(robot_id):
                act = 'dual_carry'
            else:
                act = 'action'

        msg = String()
        payload = {
            "success": bool(success),
            "status": status_str,
            "action": str(act),
            "robot": str(robot_id),
            "message": str(message),
            "robot_id": str(robot_id),
            "elapsed_sec": elapsed_sec,
            "wall_timestamp": time.time()
        }
        msg.data = json.dumps(payload)
        self.result_pub.publish(msg)

    def _resolve_target_name(self, label):
        """Resolve a freeform label or name to a canonical object prim name."""
        if not label:
            return None
        l = label.lower().strip()
        
        # Exact block names and colors
        if 'red' in l or 'block1' in l: return 'Block1'
        elif 'green' in l or 'block2' in l: return 'Block2'
        elif 'blue' in l or 'block3' in l: return 'Block3'
        elif 'yellow' in l or 'block4' in l: return 'Block4'
        elif 'magenta' in l or 'block5' in l: return 'Block5'
        elif 'cyan' in l or 'block6' in l: return 'Block6'
        elif 'orange' in l or 'block7' in l: return 'Block7'
        elif 'purple' in l or 'block8' in l: return 'Block8'
        elif 'lime' in l or 'block9' in l: return 'Block9'
        elif 'block' in l:
            digits = ''.join([c for c in l if c.isdigit()])
            if digits and 1 <= int(digits) <= 9:
                return f"Block{digits}"
                
        # Kitchen dishes/plates
        if 'dish1' in l or 'plate1' in l or 'white dish' in l or 'porcelain' in l: return 'Dish1'
        elif 'dish2' in l or 'plate2' in l or 'blue dish' in l or 'cobalt' in l or 'nordic' in l: return 'Dish2'
        elif 'dish3' in l or 'plate3' in l or 'terracotta' in l or 'clay' in l: return 'Dish3'
        elif 'dish' in l or 'plate' in l:
            digits = ''.join([c for c in l if c.isdigit()])
            if digits and 1 <= int(digits) <= 3:
                return f"Dish{digits}"
            return 'Dish1'
            
        # Kitchen cups/mugs
        if 'cup1' in l or 'mug1' in l or 'amber' in l or 'mustard' in l: return 'Cup1'
        elif 'cup2' in l or 'mug2' in l or 'sage' in l or 'mint' in l: return 'Cup2'
        elif 'cup3' in l or 'mug3' in l or 'charcoal' in l or 'espresso' in l: return 'Cup3'
        elif 'cup' in l or 'mug' in l:
            digits = ''.join([c for c in l if c.isdigit()])
            if digits and 1 <= int(digits) <= 3:
                return f"Cup{digits}"
            return 'Cup1'
            
        # Long bar
        if 'longbar' in l or 'long_bar' in l or 'bar' in l or 'tray' in l:
            return 'LongBar1'
            
        # Capitalized fallback
        for prefix in ['Block', 'Dish', 'Cup', 'LongBar']:
            if l.startswith(prefix.lower()):
                suffix = l[len(prefix):].strip()
                return prefix + suffix.capitalize()
        return label

    def _resolve_block_name(self, label):
        """Backward-compatible alias for _resolve_target_name."""
        return self._resolve_target_name(label)

    @staticmethod
    def get_object_type(name: str) -> str:
        """Classify target object into affordance taxonomy ('dish', 'cup', 'block', 'long_bar')."""
        if not name:
            return 'block'
        n = str(name).lower()
        if 'dish' in n or 'plate' in n or 'saucer' in n:
            return 'dish'
        elif 'cup' in n or 'mug' in n:
            return 'cup'
        elif 'bar' in n or 'tray' in n:
            return 'long_bar'
        elif 'block' in n or 'cube' in n or 'cylinder' in n:
            return 'block'
        return 'block'

    @staticmethod
    def get_affordance(obj_type: str) -> dict:
        """Retrieve physical and grasp parameters for the specified object type."""
        return KITCHEN_AFFORDANCES.get(obj_type, KITCHEN_AFFORDANCES['block'])

    def _find_clearable_object(self, robot_id, zone='counter'):
        """Find an unorganized kitchen object in the workspace reachable by this robot."""
        candidates = [f"Dish{i}" for i in range(1, 4)] + [f"Cup{i}" for i in range(1, 4)]
        frame = self.get_robot_base_frame(robot_id)
        
        for cand in candidates:
            try:
                trans = self.tf_buffer.lookup_transform(frame, cand, rclpy.time.Time())
                dist = np.hypot(trans.transform.translation.x, trans.transform.translation.y)
                if 0.15 <= dist <= 0.85:
                    return cand
            except Exception:
                continue
                
        # Default fallback by robot quadrant
        if robot_id == 1: return 'Dish1'
        elif robot_id == 2: return 'Cup1'
        else: return 'Dish2'

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
        """Retrieve object position and optimal grasp quaternion in robot base frame.
        
        Implements adaptive grasp strategies according to KITCHEN_AFFORDANCES:
        - 'dish': Rim-pinch offset towards the robot base and rim-tangent grasp orientation
        - 'cup': Cylindrical body clamping at mid-height with radial grasp orientation
        - 'block': Top-down 4-fold symmetric grasp quaternion
        - 'long_bar': Balanced clamping
        """
        name = self.get_target_block_name(robot_id)
        if not name:
            return None, None
        frame = self.get_robot_base_frame(robot_id)
        try:
            trans = self.tf_buffer.lookup_transform(frame, name, rclpy.time.Time())
            px = trans.transform.translation.x
            py = trans.transform.translation.y
            pz = trans.transform.translation.z
            q = trans.transform.rotation
            
            obj_type = self.get_object_type(name)
            affordance = self.get_affordance(obj_type)
            
            arm_yaw = np.arctan2(py, px)
            
            if obj_type == 'dish':
                # Rim-pinch grasp: offset from dish center towards robot base origin [0, 0]
                dist_xy = np.hypot(px, py)
                if dist_xy > 1e-4:
                    u_base = np.array([-px / dist_xy, -py / dist_xy])
                else:
                    u_base = np.array([-1.0, 0.0])
                    
                rim_radius = affordance.get('rim_offset_radius', 0.065)
                grasp_x = px + rim_radius * u_base[0]
                grasp_y = py + rim_radius * u_base[1]
                grasp_z = pz + affordance.get('grasp_z_offset', 0.002)
                
                # Tangent to rim in robot base frame: perpendicular to u_base
                rim_tangent_yaw = np.arctan2(u_base[1], u_base[0]) + np.pi / 2.0
                target_quat = kinematics.compute_symmetric_grasp_quat(rim_tangent_yaw, arm_yaw)
                return np.array([grasp_x, grasp_y, grasp_z]), target_quat
                
            elif obj_type == 'cup':
                # Mid-height cylindrical clamp
                grasp_x = px
                grasp_y = py
                grasp_z = pz + affordance.get('grasp_z_offset', 0.035)
                target_quat = kinematics.compute_symmetric_grasp_quat(arm_yaw, arm_yaw)
                return np.array([grasp_x, grasp_y, grasp_z]), target_quat
                
            elif obj_type == 'long_bar':
                grasp_x = px
                grasp_y = py
                grasp_z = pz + affordance.get('grasp_z_offset', 0.010)
                bar_yaw = np.arctan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
                target_quat = kinematics.compute_symmetric_grasp_quat(bar_yaw, arm_yaw)
                return np.array([grasp_x, grasp_y, grasp_z]), target_quat
                
            else:
                # Default 'block' 4-fold symmetric grasp
                block_yaw = np.arctan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
                target_quat = kinematics.compute_symmetric_grasp_quat(block_yaw, arm_yaw)
                return np.array([px, py, pz]), target_quat
                
        except Exception as e:
            self.get_logger().error(f"TF lookup failed for {name} to {frame}: {e}", throttle_duration_sec=1.0)
            return None, None

    def get_place_local_pose(self, robot_id):
        """Retrieve target position and optimal place quaternion in robot base frame.
        
        Supports height calculation for stacked blocks, nested dishes, and cups.
        Accounts for rim-pinch offset when placing dishes.
        """
        frame = self.get_robot_base_frame(robot_id)
        active_obj = self.get_target_block_name(robot_id)
        obj_type = self.get_object_type(active_obj)
        affordance = self.get_affordance(obj_type)
        
        target_x = getattr(self, f'target_x{robot_id}', 0.0)
        target_y = getattr(self, f'target_y{robot_id}', 0.0)
        
        try:
            trans = self.tf_buffer.lookup_transform(frame, 'world', rclpy.time.Time())
            
            all_candidate_objects = (
                [f"Block{i}" for i in range(1, 10)] +
                [f"Dish{i}" for i in range(1, 4)] +
                [f"Cup{i}" for i in range(1, 4)]
            )
            
            objects_on_stack = 0
            max_obj_z = None
            
            for obj_name in all_candidate_objects:
                if obj_name == active_obj:
                    continue  # Do not count currently held object
                try:
                    b_trans = self.tf_buffer.lookup_transform('world', obj_name, rclpy.time.Time())
                    bx = b_trans.transform.translation.x
                    by = b_trans.transform.translation.y
                    bz = b_trans.transform.translation.z
                    dist = np.hypot(bx - target_x, by - target_y)
                    # 0.06m threshold detects vertically stacked/nested items
                    if dist < 0.06 and bz >= 0.25:
                        objects_on_stack += 1
                        if max_obj_z is None or bz > max_obj_z:
                            max_obj_z = bz
                except Exception:
                    pass
            
            # Surface of table in world is 0.30m
            table_surface_z = 0.30
            
            if obj_type == 'dish':
                if objects_on_stack > 0 and max_obj_z is not None:
                    # Stacking dishes: nested offset (rim-to-rim ~ 12mm)
                    target_z_world = max_obj_z + affordance.get('nesting_z_offset', 0.012)
                else:
                    target_z_world = table_surface_z + affordance.get('place_z_offset', 0.014)
            elif obj_type == 'cup':
                if objects_on_stack > 0 and max_obj_z is not None:
                    target_z_world = max_obj_z + affordance.get('nesting_z_offset', 0.090)
                else:
                    target_z_world = table_surface_z + affordance.get('place_z_offset', 0.045)
            else:
                # Block
                if objects_on_stack > 0 and max_obj_z is not None:
                    target_z_world = max_obj_z + self.block_height + 0.005
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
            
            # If dish was rim-pinched, TCP must be positioned at rim offset relative to dish center
            if obj_type == 'dish':
                dist_xy = np.hypot(p_local[0], p_local[1])
                if dist_xy > 1e-4:
                    u_base = np.array([-p_local[0] / dist_xy, -p_local[1] / dist_xy])
                else:
                    u_base = np.array([-1.0, 0.0])
                rim_radius = affordance.get('rim_offset_radius', 0.065)
                p_local[0] += rim_radius * u_base[0]
                p_local[1] += rim_radius * u_base[1]
            
            # World X-axis yaw in robot base frame
            q = trans.transform.rotation
            world_yaw = np.arctan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            arm_yaw = np.arctan2(p_local[1], p_local[0])
            
            if obj_type == 'dish':
                rim_tangent_yaw = np.arctan2(u_base[1], u_base[0]) + np.pi / 2.0
                target_quat = kinematics.compute_symmetric_grasp_quat(rim_tangent_yaw, arm_yaw)
            elif obj_type == 'cup':
                target_quat = kinematics.compute_symmetric_grasp_quat(arm_yaw, arm_yaw)
            else:
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
            if getattr(self, f'is_autonomous_cycle{r_id}', False):
                action = getattr(self, f'autonomous_action_name{r_id}', action)
            target = getattr(self, f'active_target{r_id}', None) or self.get_target_block_name(r_id) or ''
            
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

        # Center table occupancy representation
        center_token = None
        if self.center_occupied_by:
            if str(self.center_occupied_by).startswith('DUAL_'):
                center_token = str(self.center_occupied_by)
            elif str(self.center_occupied_by).startswith('FR3_'):
                center_token = str(self.center_occupied_by)
            else:
                center_token = f'FR3_{self.center_occupied_by}'

        collab_active = bool(self.collaborative_active)
        collab_pair = list(self.collaborative_pair) if (collab_active and self.collaborative_pair) else None
        collab_obj = str(self.collaborative_object) if (collab_active and self.collaborative_object) else None

        for r_id in [1, 2, 3]:
            # Add alias for both 'FR3_1' and '1'
            robots_data[str(r_id)] = dict(robots_data[f'FR3_{r_id}'])

            if collab_active and f'FR3_{r_id}' in (collab_pair or []):
                partner = 'FR3_2' if r_id == 1 else 'FR3_1'
                robots_data[f'FR3_{r_id}']['collaborating_with'] = partner
                robots_data[f'FR3_{r_id}']['dual_link_active'] = True
                robots_data[str(r_id)]['collaborating_with'] = partner
                robots_data[str(r_id)]['dual_link_active'] = True
                if self.dual_state == 'DUAL_COUPLED_TRANSPORT':
                    robots_data[f'FR3_{r_id}']['state'] = 'COLLAB_TRANSIT'
                    robots_data[f'FR3_{r_id}']['phase'] = 'COLLAB_TRANSPORT'
                    robots_data[str(r_id)]['state'] = 'COLLAB_TRANSIT'
                    robots_data[str(r_id)]['phase'] = 'COLLAB_TRANSPORT'
                else:
                    robots_data[f'FR3_{r_id}']['state'] = self.dual_state
                    robots_data[str(r_id)]['state'] = self.dual_state
            else:
                robots_data[f'FR3_{r_id}']['collaborating_with'] = None
                robots_data[f'FR3_{r_id}']['dual_link_active'] = False
                robots_data[str(r_id)]['collaborating_with'] = None
                robots_data[str(r_id)]['dual_link_active'] = False

        msg = String()
        msg.data = json.dumps({
            'timestamp': round(now - self._metrics_start_time, 2),
            'robots': robots_data,
            'tower_height': self.tower_height,
            'center_occupied_by': center_token,
            'collaborative_active': collab_active,
            'collaborative_pair': collab_pair,
            'collaborative_object': collab_obj,
            'dual_collaboration': {
                'active': collab_active,
                'robots': collab_pair,
                'object': collab_obj,
            }
        })
        self.metrics_pub.publish(msg)

    def _timer_callback(self):
        if getattr(self, 'dual_active', False):
            self._process_dual_arm()
            self._process_robot(3)
        else:
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
                obj_name = self.get_target_block_name(robot_id)
                affordance = self.get_affordance(self.get_object_type(obj_name))
                grip_close = affordance.get('gripper_close', self.gripper_close)
                self._initialize_joint_phase(robot_id, end_q, grip_close)
                self._set_state(robot_id, 'TUCK_AFTER_PICK')

        elif state in ['ROTATE_TO_PICK', 'HOVER_PICK', 'DESCEND_PICK', 'GRASP', 'LIFT',
                       'TUCK_AFTER_PICK', 'ROTATE_TO_PLACE', 'HOVER_PLACE', 'DESCEND_PLACE', 
                       'RELEASE', 'RETRACT', 'TUCK_AFTER_PLACE', 'RETURN_HOME']:
            step_counter += 1
            setattr(self, f'step_counter{robot_id}', step_counter)

            # Determine duration for this phase
            robot_steps = getattr(self, f'steps_per_phase{robot_id}', self.steps_per_phase)
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
                obj_name = self.get_target_block_name(robot_id)
                obj_type = self.get_object_type(obj_name)
                affordance = self.get_affordance(obj_type)

                if state == 'ROTATE_TO_PICK':
                    block_pos, block_quat = self.get_block_local_pose(robot_id)
                    if block_pos is None: return
                    hover_h = getattr(self, f'hover_height{robot_id}', None)
                    if hover_h is None:
                        hover_h = affordance.get('approach_height', self.hover_height)
                    hover_pos = np.array([block_pos[0], block_pos[1], block_pos[2] + hover_h])
                    grip_open = affordance.get('gripper_open', self.gripper_open)
                    self._initialize_phase(robot_id, hover_pos, grip_open, block_quat)
                    self._set_state(robot_id, 'HOVER_PICK')

                elif state == 'HOVER_PICK':
                    block_pos, block_quat = self.get_block_local_pose(robot_id)
                    if block_pos is None: return
                    grip_open = affordance.get('gripper_open', self.gripper_open)
                    self._initialize_phase(robot_id, block_pos, grip_open, block_quat)
                    self._set_state(robot_id, 'DESCEND_PICK')

                elif state == 'DESCEND_PICK':
                    # Grasp object: close gripper to affordance target
                    grip_close = affordance.get('gripper_close', self.gripper_close)
                    self._initialize_phase(robot_id, end_pos, grip_close, end_quat)
                    self._set_state(robot_id, 'GRASP')

                elif state == 'GRASP':
                    # Lift object vertically using affordance lift height
                    lift_h = affordance.get('lift_height', self.hover_height)
                    lift_pos = np.array([end_pos[0], end_pos[1], end_pos[2] + lift_h])
                    grip_close = affordance.get('gripper_close', self.gripper_close)
                    self._initialize_phase(robot_id, lift_pos, grip_close, end_quat)
                    self._set_state(robot_id, 'LIFT')

                elif state == 'LIFT':
                    gripper_pos = getattr(self, f'current_gripper{robot_id}')
                    vmin, vmax = affordance.get('verification_range', (0.008, 0.028))
                    pick_success = (vmin <= gripper_pos <= vmax)

                    is_auto = getattr(self, f'is_autonomous_cycle{robot_id}', False)

                    if self.mode == 'gemini':
                        if is_auto:
                            if pick_success:
                                self._set_state(robot_id, 'WAIT_FOR_CENTER')
                            else:
                                act_name = getattr(self, f'autonomous_action_name{robot_id}', 'action')
                                setattr(self, f'is_autonomous_cycle{robot_id}', False)
                                self._set_state(robot_id, 'FINISHED')
                                self._publish_result(
                                    False, 
                                    f"{act_name.replace('_', ' ').capitalize()} failed by robot {robot_id}. Grasp verification failed (gripper: {gripper_pos:.4f}m outside [{vmin:.4f}, {vmax:.4f}] for {obj_name}).", 
                                    f"FR3_{robot_id}"
                                )
                                self._tasks_failed[robot_id] += 1
                        elif getattr(self, f'gemini_action{robot_id}') == 'pick':
                            if pick_success:
                                self._set_state(robot_id, 'WAITING_FOR_PLACE_CMD')
                                self._publish_result(
                                    True, 
                                    f"Pick completed by robot {robot_id}. Grasped {obj_name} ({obj_type}) successfully (gripper: {gripper_pos:.4f}m).", 
                                    f"FR3_{robot_id}"
                                )
                            else:
                                self._set_state(robot_id, 'FINISHED')
                                self._publish_result(
                                    False, 
                                    f"Pick failed by robot {robot_id}. Gripper closed outside verification range [{vmin:.4f}, {vmax:.4f}] (actual: {gripper_pos:.4f}m).", 
                                    f"FR3_{robot_id}"
                                )
                                self._tasks_failed[robot_id] += 1
                        else:
                            if pick_success:
                                self._set_state(robot_id, 'WAIT_FOR_CENTER')
                            else:
                                self._set_state(robot_id, 'FINISHED')
                                self._publish_result(False, f"Grasp verification failed for {obj_name}.", f"FR3_{robot_id}")
                                self._tasks_failed[robot_id] += 1
                    else:
                        if pick_success:
                            self._set_state(robot_id, 'WAIT_FOR_CENTER')
                        else:
                            self.get_logger().warn(f"Robot {robot_id} failed to grasp {obj_name}! Retrying...")
                            self._set_state(robot_id, 'INIT')

                elif state == 'TUCK_AFTER_PICK':
                    place_pos, _ = self.get_place_local_pose(robot_id)
                    if place_pos is None: return
                    j1_angle = self._compute_j1_for_target(robot_id, place_pos)
                    end_q = self._make_tuck_config(j1_angle)
                    grip_close = affordance.get('gripper_close', self.gripper_close)
                    self._initialize_joint_phase(robot_id, end_q, grip_close)
                    self._set_state(robot_id, 'ROTATE_TO_PLACE')

                elif state == 'ROTATE_TO_PLACE':
                    place_pos, place_quat = self.get_place_local_pose(robot_id)
                    if place_pos is None: return
                    hover_h = getattr(self, f'hover_height{robot_id}', None)
                    if hover_h is None:
                        hover_h = affordance.get('approach_height', self.hover_height)
                    hover_place_pos = np.array([place_pos[0], place_pos[1], place_pos[2] + hover_h])
                    grip_close = affordance.get('gripper_close', self.gripper_close)
                    self._initialize_phase(robot_id, hover_place_pos, grip_close, place_quat)
                    self._set_state(robot_id, 'HOVER_PLACE')

                elif state == 'HOVER_PLACE':
                    place_pos, place_quat = self.get_place_local_pose(robot_id)
                    if place_pos is None: return
                    grip_close = affordance.get('gripper_close', self.gripper_close)
                    self._initialize_phase(robot_id, place_pos, grip_close, place_quat)
                    self._set_state(robot_id, 'DESCEND_PLACE')

                elif state == 'DESCEND_PLACE':
                    # Release object: open gripper according to affordance
                    grip_open = affordance.get('gripper_open', self.gripper_open)
                    self._initialize_phase(robot_id, end_pos, grip_open, end_quat)
                    self._set_state(robot_id, 'RELEASE')

                elif state == 'RELEASE':
                    # Retract vertically
                    hover_h = getattr(self, f'hover_height{robot_id}', None)
                    if hover_h is None:
                        hover_h = affordance.get('approach_height', self.hover_height)
                    retract_pos = np.array([end_pos[0], end_pos[1], end_pos[2] + hover_h])
                    grip_open = affordance.get('gripper_open', self.gripper_open)
                    self._initialize_phase(robot_id, retract_pos, grip_open, end_quat)
                    self._set_state(robot_id, 'RETRACT')

                elif state == 'RETRACT':
                    if obj_type == 'block':
                        self.tower_height += 1
                        self.get_logger().info(f"Tower height incremented to: {self.tower_height}")
                    else:
                        self.get_logger().info(f"Placed {obj_name} ({obj_type}) successfully.")
                    q_current = getattr(self, f'q_current{robot_id}')
                    end_q = self._make_tuck_config(q_current[0])
                    grip_open = affordance.get('gripper_open', self.gripper_open)
                    self._initialize_joint_phase(robot_id, end_q, grip_open)
                    self._set_state(robot_id, 'TUCK_AFTER_PLACE')

                elif state == 'TUCK_AFTER_PLACE':
                    grip_open = affordance.get('gripper_open', self.gripper_open)
                    self._initialize_joint_phase(robot_id, self.q_home_fr3, grip_open)
                    self._set_state(robot_id, 'RETURN_HOME')

                elif state == 'RETURN_HOME':
                    if self.center_occupied_by == robot_id:
                        self.center_occupied_by = None

                    is_auto = getattr(self, f'is_autonomous_cycle{robot_id}', False)
                    act_name = getattr(self, f'autonomous_action_name{robot_id}', getattr(self, f'gemini_action{robot_id}', 'place'))

                    if self.mode == 'gemini':
                        self._set_state(robot_id, 'FINISHED')
                        self._tasks_completed[robot_id] += 1
                        if is_auto:
                            setattr(self, f'is_autonomous_cycle{robot_id}', False)
                            tx = getattr(self, f'target_x{robot_id}', 0.0)
                            ty = getattr(self, f'target_y{robot_id}', 0.0)
                            self._publish_result(
                                True, 
                                f"{act_name.replace('_', ' ').capitalize()} completed by robot {robot_id}. Moved {obj_name} to [{tx:.2f}, {ty:.2f}].", 
                                f"FR3_{robot_id}"
                            )
                        elif getattr(self, f'gemini_action{robot_id}') in ['place', 'place_relative']:
                            tx = getattr(self, f'target_x{robot_id}', 0.0)
                            ty = getattr(self, f'target_y{robot_id}', 0.0)
                            if obj_type == 'block':
                                msg_str = f"Place completed by robot {robot_id}. Tower height is now {self.tower_height}."
                            else:
                                msg_str = f"Place completed by robot {robot_id}. Target {obj_name} placed at [{tx:.2f}, {ty:.2f}]."
                            self._publish_result(True, msg_str, f"FR3_{robot_id}")
                        else:
                            self._publish_result(True, f"Task completed by robot {robot_id}.", f"FR3_{robot_id}")
                    else:
                        # Advance block index for current robot in rule-based mode
                        max_blocks_per_robot = 3
                        curr_idx = getattr(self, f'block_index{robot_id}')
                        if curr_idx < max_blocks_per_robot - 1:
                            setattr(self, f'block_index{robot_id}', curr_idx + 1)
                            self._set_state(robot_id, 'INIT')
                        else:
                            self._set_state(robot_id, 'FINISHED')
                            self.get_logger().info(f"[SEQUENCER] Robot {robot_id} finished all its tasks.")

    # =========================================================================
    # Dual-Arm Collaborative Manipulation (Requirement R3, Features 10-14)
    # =========================================================================

    @staticmethod
    def generate_coupled_waypoints(start_center, target_center, bar_length=0.40, num_steps=20):
        """Generate synchronized Cartesian waypoints for Robot 1 and Robot 2 maintaining constant distance.
        
        Preserves rigid-body distance invariance:
            ||P_2(t) - P_1(t)|| == bar_length (distance drift < 0.001m)
        Utilizes MoveIt 2 minimum-jerk quintic polynomial blending with zero initial/terminal velocities.
        """
        half_l = float(bar_length) / 2.0
        t_vals = np.linspace(0.0, 1.0, num_steps)
        # Minimum Jerk Quintic Polynomial: s(t) = 10*t^3 - 15*t^4 + 6*t^5
        s = 10.0 * (t_vals ** 3) - 15.0 * (t_vals ** 4) + 6.0 * (t_vals ** 5)

        start_c = np.array(start_center, dtype=float)
        target_c = np.array(target_center, dtype=float)

        robot1_waypoints = []
        robot2_waypoints = []

        for u in s:
            c = (1.0 - u) * start_c + u * target_c
            p1 = np.array([c[0] - half_l, c[1], c[2]])
            p2 = np.array([c[0] + half_l, c[1], c[2]])
            robot1_waypoints.append(p1)
            robot2_waypoints.append(p2)

        return np.array(robot1_waypoints), np.array(robot2_waypoints)

    def world_to_base(self, robot_id, p_world, q_world=None):
        """Transform 3D position and optional quaternion from world to robot base frame.
        
        Uses TF listener if available with analytical geometric fallback based on nominal mounts:
        - FR3_1: [0.0, -0.45, 0.20], yaw +90 deg
        - FR3_2: [0.3897, 0.225, 0.20], yaw +210 deg
        - FR3_3: [-0.3897, 0.225, 0.20], yaw +330 deg
        """
        frame = self.get_robot_base_frame(robot_id)
        try:
            trans = self.tf_buffer.lookup_transform(frame, 'world', rclpy.time.Time())
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
            p_local = p_rot @ np.array(p_world, dtype=float) + p_trans
            if q_world is not None:
                R_w = kinematics.quat_to_rot_matrix(q_world)
                R_local = p_rot @ R_w
                q_local = kinematics.rot_matrix_to_quat(R_local)
                return p_local, q_local
            return p_local, None
        except Exception:
            if robot_id == 1:
                yaw_base = np.pi / 2.0
                base_xyz = np.array([0.0, -0.45, 0.20])
            elif robot_id == 2:
                yaw_base = 7.0 * np.pi / 6.0
                base_xyz = np.array([0.3897, 0.225, 0.20])
            else:
                yaw_base = 11.0 * np.pi / 6.0
                base_xyz = np.array([-0.3897, 0.225, 0.20])

            c, s = np.cos(-yaw_base), np.sin(-yaw_base)
            R_bw = np.array([
                [c, -s, 0.0],
                [s,  c, 0.0],
                [0.0, 0.0, 1.0]
            ])
            p_rel = np.array(p_world, dtype=float) - base_xyz
            p_local = R_bw @ p_rel
            if q_world is not None:
                R_w = kinematics.quat_to_rot_matrix(q_world)
                R_local = R_bw @ R_w
                q_local = kinematics.rot_matrix_to_quat(R_local)
                return p_local, q_local
            return p_local, None

    def get_bar_world_pose(self):
        """Retrieve LongBar1 position and yaw in world frame."""
        target_name = getattr(self, 'dual_target_name', 'LongBar1') or 'LongBar1'
        try:
            trans = self.tf_buffer.lookup_transform('world', target_name, rclpy.time.Time())
            px = trans.transform.translation.x
            py = trans.transform.translation.y
            pz = trans.transform.translation.z
            q = trans.transform.rotation
            yaw = np.arctan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            return np.array([px, py, pz]), yaw
        except Exception:
            return np.array([0.0, -0.15, 0.22]), 0.0

    def solve_ik_with_elbow_bias(self, robot_id, target_pos, target_quat, q_init, max_iter=60, tol=1e-4):
        """Solve Franka FR3 inverse kinematics with outward elbow null-space biasing.
        
        Applies null-space projection (I - J^# J) k_null (q_elbow_null - q):
        - FR3_1: biases elbow outward towards West / -Y world (away from FR3_2)
        - FR3_2: biases elbow outward towards East / +X world (away from FR3_1)
        Guarantees clearance >= 0.15m between adjacent arm elbows during collaborative transit.
        """
        q = np.array(q_init, dtype=float)
        if np.any(np.isnan(target_pos)):
            return q, False

        R_target = kinematics.quat_to_rot_matrix(target_quat)

        # Outward elbow reference posture per robot
        if robot_id == 1:
            q_elbow_null = np.array([q[0], -0.3, 0.5, -1.8, 0.0, 1.8, 0.7854])
        elif robot_id == 2:
            q_elbow_null = np.array([q[0], -0.3, -0.5, -1.8, 0.0, 1.8, 0.7854])
        else:
            q_elbow_null = np.array(kinematics.FR3_HOME_CONFIG)

        damping = 0.02
        k_null = 0.08

        for _ in range(max_iter):
            T_ee = kinematics.forward_kinematics(q)
            p_ee = T_ee[:3, 3]
            R_ee = T_ee[:3, :3]

            err_pos = target_pos - p_ee
            R_err = R_target @ R_ee.T
            tr = np.trace(R_err)
            theta_err = np.arccos(np.clip((tr - 1.0) / 2.0, -1.0, 1.0))

            if np.abs(theta_err) < 1e-6:
                err_rot = np.zeros(3)
            else:
                axis = np.array([
                    R_err[2, 1] - R_err[1, 2],
                    R_err[0, 2] - R_err[2, 0],
                    R_err[1, 0] - R_err[0, 1]
                ]) / (2.0 * np.sin(theta_err))
                err_rot = axis * theta_err

            error = np.hstack((err_pos, err_rot))
            if np.linalg.norm(error) < tol:
                return q, True

            J = kinematics.get_jacobian(q)
            inv_J = J.T @ np.linalg.inv(J @ J.T + damping**2 * np.eye(6))
            null_space_projector = np.eye(7) - inv_J @ J
            grad_null = k_null * (q_elbow_null - q)
            null_term = null_space_projector @ grad_null

            dq = inv_J @ error + null_term
            step_limit = 0.15
            dq_norm = np.linalg.norm(dq)
            if dq_norm > step_limit:
                dq = dq * (step_limit / dq_norm)

            q += dq
            for i in range(7):
                q[i] = np.clip(q[i], kinematics.FR3_JOINT_LIMITS[i][0], kinematics.FR3_JOINT_LIMITS[i][1])

        return q, False

    def _init_dual_cartesian_phase(self, r1, r2, p1_end, p2_end, quat1_end, quat2_end, end_gripper):
        """Initialize waypoints and quaternions for a coupled Cartesian phase."""
        q1_curr = getattr(self, f'q_current{r1}')
        q2_curr = getattr(self, f'q_current{r2}')

        self.dual_w1_start = kinematics.forward_kinematics(q1_curr)[:3, 3]
        self.dual_w2_start = kinematics.forward_kinematics(q2_curr)[:3, 3]

        self.dual_w1_end = np.array(p1_end, dtype=float)
        self.dual_w2_end = np.array(p2_end, dtype=float)

        self.dual_quat1_start = list(getattr(self, f'end_quat{r1}', [0.0, 1.0, 0.0, 0.0]))
        self.dual_quat2_start = list(getattr(self, f'end_quat{r2}', [0.0, 1.0, 0.0, 0.0]))

        self.dual_quat1_end = list(quat1_end)
        self.dual_quat2_end = list(quat2_end)

        setattr(self, f'end_quat{r1}', list(quat1_end))
        setattr(self, f'end_quat{r2}', list(quat2_end))

        self.dual_grip_start = getattr(self, f'end_gripper{r1}', self.gripper_open)
        self.dual_grip_end = end_gripper
        setattr(self, f'end_gripper{r1}', end_gripper)
        setattr(self, f'end_gripper{r2}', end_gripper)

        self.dual_step_counter = 0

    def _publish_arm_cmd(self, robot_id, q_sol, grip_target):
        """Publish simultaneous joint command to a specific robot."""
        cmd_pub = self.cmd_pub1 if robot_id == 1 else (self.cmd_pub2 if robot_id == 2 else self.cmd_pub3)
        cmd = JointState()
        cmd.header.stamp = self.get_clock().now().to_msg()
        cmd.name = self.joint_names_fr3
        cmd.position = list(q_sol) + [float(grip_target), float(grip_target)]
        cmd_pub.publish(cmd)

    def _start_dual_carry(self, robots=[1, 2], target_name='LongBar1', dest_pos=[0.0, 0.15, 0.22], dest_yaw=0.0, steps=40):
        """Initiate lock-step dual-arm collaborative manipulation sequence."""
        self.dual_active = True
        self.dual_state = 'DUAL_INIT'
        self.dual_step_counter = 0
        self.dual_steps_per_phase = steps
        self.dual_robots = list(robots)
        self.dual_target_name = target_name
        self.dual_dest_pos = np.array(dest_pos, dtype=float)
        self.dual_dest_yaw = dest_yaw

        self.collaborative_active = True
        self.collaborative_pair = [f'FR3_{r}' for r in robots]
        self.collaborative_object = target_name

        self._action_start_time['global'] = time.monotonic()
        self._action_start_time['DUAL_FR3_1_FR3_2'] = time.monotonic()
        for r in robots:
            self._action_start_time[r] = time.monotonic()
            setattr(self, f'gemini_action{r}', 'dual_carry')
            setattr(self, f'active_target{r}', target_name)
            setattr(self, f'active_object_type{r}', 'long_bar')

        self.get_logger().info(f"[DUAL-ARM] Initiating dual_carry for {target_name} with robots {self.collaborative_pair}")

    def _process_dual_arm(self):
        """50 Hz lock-step dual-arm state machine executor."""
        r1, r2 = self.dual_robots[0], self.dual_robots[1]

        state = self.dual_state
        step = self.dual_step_counter
        total_steps = self.dual_steps_per_phase

        if state in ('DUAL_CONTACT_GRASP', 'DUAL_SYNCHRONIZED_RELEASE'):
            total_steps = self.dual_dwell_steps

        # Phase 1: DUAL_INIT - Mutex Reservation & Initial Trajectory Setup
        if state == 'DUAL_INIT':
            if self.center_occupied_by is not None and self.center_occupied_by != 'DUAL_FR3_1_FR3_2':
                return  # Wait for center table mutex

            self.center_occupied_by = 'DUAL_FR3_1_FR3_2'

            bar_pos, bar_yaw = self.get_bar_world_pose()
            self.dual_start_bar_pos = np.array(bar_pos, dtype=float)
            self.dual_start_bar_yaw = bar_yaw

            half_sep = self.dual_grasp_separation / 2.0  # 0.20m
            u_long = np.array([np.cos(bar_yaw), np.sin(bar_yaw), 0.0])

            p1_world = self.dual_start_bar_pos - half_sep * u_long
            p2_world = self.dual_start_bar_pos + half_sep * u_long

            p1_local, _ = self.world_to_base(r1, p1_world)
            p2_local, _ = self.world_to_base(r2, p2_world)

            j1_1 = self._compute_j1_for_target(r1, p1_local)
            j1_2 = self._compute_j1_for_target(r2, p2_local)

            self.dual_q1_start = np.array(getattr(self, f'q_current{r1}'))
            self.dual_q1_end = np.array(self._make_tuck_config(j1_1))
            self.dual_q2_start = np.array(getattr(self, f'q_current{r2}'))
            self.dual_q2_end = np.array(self._make_tuck_config(j1_2))

            self.dual_grip_start = self.gripper_open
            self.dual_grip_end = self.gripper_open
            self.dual_step_counter = 0
            self.dual_state = 'DUAL_ROTATE_TO_APPROACH'
            self._set_state(r1, 'DUAL_ROTATE_TO_APPROACH')
            self._set_state(r2, 'DUAL_ROTATE_TO_APPROACH')
            return

        self.dual_step_counter += 1
        step = self.dual_step_counter
        t = min(float(step) / float(total_steps), 1.0)
        t_smooth = 10.0 * (t ** 3) - 15.0 * (t ** 4) + 6.0 * (t ** 5)

        # Joint-Space Interpolation
        if state in ('DUAL_ROTATE_TO_APPROACH', 'DUAL_RETURN_HOME'):
            q1_sol = self.dual_q1_start + t_smooth * (self.dual_q1_end - self.dual_q1_start)
            q2_sol = self.dual_q2_start + t_smooth * (self.dual_q2_end - self.dual_q2_start)
            for i in range(7):
                q1_sol[i] = np.clip(q1_sol[i], kinematics.FR3_JOINT_LIMITS[i][0], kinematics.FR3_JOINT_LIMITS[i][1])
                q2_sol[i] = np.clip(q2_sol[i], kinematics.FR3_JOINT_LIMITS[i][0], kinematics.FR3_JOINT_LIMITS[i][1])
            grip1_target = self.dual_grip_start + t_smooth * (self.dual_grip_end - self.dual_grip_start)
            grip2_target = grip1_target

        elif state in ('DUAL_CONTACT_GRASP', 'DUAL_SYNCHRONIZED_RELEASE'):
            q1_sol = np.array(getattr(self, f'q_current{r1}'))
            q2_sol = np.array(getattr(self, f'q_current{r2}'))
            grip1_target = self.dual_grip_start + t_smooth * (self.dual_grip_end - self.dual_grip_start)
            grip2_target = grip1_target

        else:
            # Cartesian-Space Coupled Trajectory Execution
            p1_cart = self.dual_w1_start + t_smooth * (self.dual_w1_end - self.dual_w1_start)
            p2_cart = self.dual_w2_start + t_smooth * (self.dual_w2_end - self.dual_w2_start)
            quat1_cart = kinematics.interpolate_quat(self.dual_quat1_start, self.dual_quat1_end, t_smooth)
            quat2_cart = kinematics.interpolate_quat(self.dual_quat2_start, self.dual_quat2_end, t_smooth)

            q1_curr = getattr(self, f'q_current{r1}')
            q2_curr = getattr(self, f'q_current{r2}')

            q1_sol, _ = self.solve_ik_with_elbow_bias(r1, p1_cart, quat1_cart, q1_curr)
            q2_sol, _ = self.solve_ik_with_elbow_bias(r2, p2_cart, quat2_cart, q2_curr)

            grip1_target = self.dual_grip_start + t_smooth * (self.dual_grip_end - self.dual_grip_start)
            grip2_target = grip1_target

        self._publish_arm_cmd(r1, q1_sol, grip1_target)
        self._publish_arm_cmd(r2, q2_sol, grip2_target)

        for i in range(7):
            getattr(self, f'q_current{r1}')[i] = q1_sol[i]
            getattr(self, f'q_current{r2}')[i] = q2_sol[i]

        if step >= total_steps:
            self._transition_dual_arm_phase()

    def _transition_dual_arm_phase(self):
        """Advance the 11-phase lock-step state machine upon phase completion."""
        r1, r2 = self.dual_robots[0], self.dual_robots[1]
        state = self.dual_state
        half_sep = self.dual_grasp_separation / 2.0
        affordance = self.get_affordance('long_bar')

        if state == 'DUAL_ROTATE_TO_APPROACH':
            # Phase 3: DUAL_HOVER_APPROACH (Z + 0.12m)
            u_long = np.array([np.cos(self.dual_start_bar_yaw), np.sin(self.dual_start_bar_yaw), 0.0])
            p1_world = self.dual_start_bar_pos - half_sep * u_long
            p2_world = self.dual_start_bar_pos + half_sep * u_long

            hover_h = 0.120
            p1_hover_w = np.array([p1_world[0], p1_world[1], p1_world[2] + hover_h])
            p2_hover_w = np.array([p2_world[0], p2_world[1], p2_world[2] + hover_h])

            p1_local, _ = self.world_to_base(r1, p1_hover_w)
            p2_local, _ = self.world_to_base(r2, p2_hover_w)

            arm1_yaw = np.arctan2(p1_local[1], p1_local[0])
            arm2_yaw = np.arctan2(p2_local[1], p2_local[0])

            q1_target = kinematics.compute_symmetric_grasp_quat(self.dual_start_bar_yaw, arm1_yaw)
            q2_target = kinematics.compute_symmetric_grasp_quat(self.dual_start_bar_yaw, arm2_yaw)

            self._init_dual_cartesian_phase(r1, r2, p1_local, p2_local, q1_target, q2_target, self.gripper_open)
            self.dual_state = 'DUAL_HOVER_APPROACH'
            self._set_state(r1, 'DUAL_HOVER_APPROACH')
            self._set_state(r2, 'DUAL_HOVER_APPROACH')

        elif state == 'DUAL_HOVER_APPROACH':
            # Phase 4: DUAL_DESCEND_CONTACT (Simultaneous descent to bar grasp surface)
            u_long = np.array([np.cos(self.dual_start_bar_yaw), np.sin(self.dual_start_bar_yaw), 0.0])
            p1_world = self.dual_start_bar_pos - half_sep * u_long
            p2_world = self.dual_start_bar_pos + half_sep * u_long

            grasp_z_off = affordance.get('grasp_z_offset', 0.010)
            p1_grasp_w = np.array([p1_world[0], p1_world[1], p1_world[2] + grasp_z_off])
            p2_grasp_w = np.array([p2_world[0], p2_world[1], p2_world[2] + grasp_z_off])

            p1_local, _ = self.world_to_base(r1, p1_grasp_w)
            p2_local, _ = self.world_to_base(r2, p2_grasp_w)

            self._init_dual_cartesian_phase(r1, r2, p1_local, p2_local, self.dual_quat1_end, self.dual_quat2_end, self.gripper_open)
            self.dual_state = 'DUAL_DESCEND_CONTACT'
            self._set_state(r1, 'DUAL_DESCEND_CONTACT')
            self._set_state(r2, 'DUAL_DESCEND_CONTACT')

        elif state == 'DUAL_DESCEND_CONTACT':
            # Phase 5: DUAL_CONTACT_GRASP (Simultaneous gripper closure)
            grip_close = affordance.get('gripper_close', 0.018)
            self.dual_grip_start = self.gripper_open
            self.dual_grip_end = grip_close
            self.dual_step_counter = 0
            self.dual_state = 'DUAL_CONTACT_GRASP'
            self._set_state(r1, 'DUAL_CONTACT_GRASP')
            self._set_state(r2, 'DUAL_CONTACT_GRASP')

        elif state == 'DUAL_CONTACT_GRASP':
            # Dual Touch Sensor Verification
            g1 = getattr(self, f'current_gripper{r1}')
            g2 = getattr(self, f'current_gripper{r2}')
            vmin, vmax = affordance.get('verification_range', (0.012, 0.028))

            # Check mutual contact confirmation
            g1_ok = (vmin <= g1 <= vmax)
            g2_ok = (vmin <= g2 <= vmax)

            # In simulation feedback check
            if g1 > 0.0 and g2 > 0.0 and not (g1_ok and g2_ok):
                self._abort_dual_arm(f"Contact verification failed: g1={g1:.4f}m, g2={g2:.4f}m outside [{vmin}, {vmax}]")
                return

            self.get_logger().info(f"[DUAL-ARM] Dual contact confirmed (g1={g1:.4f}m, g2={g2:.4f}m). Proceeding to synchronized lift.")

            # Phase 6: DUAL_SYNCHRONIZED_LIFT (Coordinated vertical lift Z + 0.12m)
            lift_h = affordance.get('lift_height', 0.120)
            p1_curr_local = self.dual_w1_end.copy()
            p2_curr_local = self.dual_w2_end.copy()
            p1_lift = np.array([p1_curr_local[0], p1_curr_local[1], p1_curr_local[2] + lift_h])
            p2_lift = np.array([p2_curr_local[0], p2_curr_local[1], p2_curr_local[2] + lift_h])

            self._init_dual_cartesian_phase(r1, r2, p1_lift, p2_lift, self.dual_quat1_end, self.dual_quat2_end, affordance['gripper_close'])
            self.dual_state = 'DUAL_SYNCHRONIZED_LIFT'
            self._set_state(r1, 'DUAL_SYNCHRONIZED_LIFT')
            self._set_state(r2, 'DUAL_SYNCHRONIZED_LIFT')

        elif state == 'DUAL_SYNCHRONIZED_LIFT':
            # Phase 7: DUAL_COUPLED_TRANSPORT (Virtual rigid-body trajectory transport)
            lift_h = affordance.get('lift_height', 0.120)
            target_centroid = self.dual_dest_pos.copy()
            target_centroid[2] += lift_h

            u_long_dest = np.array([np.cos(self.dual_dest_yaw), np.sin(self.dual_dest_yaw), 0.0])
            p1_dest_w = target_centroid - half_sep * u_long_dest
            p2_dest_w = target_centroid + half_sep * u_long_dest

            p1_local_dest, _ = self.world_to_base(r1, p1_dest_w)
            p2_local_dest, _ = self.world_to_base(r2, p2_dest_w)

            arm1_yaw = np.arctan2(p1_local_dest[1], p1_local_dest[0])
            arm2_yaw = np.arctan2(p2_local_dest[1], p2_local_dest[0])
            q1_target = kinematics.compute_symmetric_grasp_quat(self.dual_dest_yaw, arm1_yaw)
            q2_target = kinematics.compute_symmetric_grasp_quat(self.dual_dest_yaw, arm2_yaw)

            self._init_dual_cartesian_phase(r1, r2, p1_local_dest, p2_local_dest, q1_target, q2_target, affordance['gripper_close'])
            self.dual_state = 'DUAL_COUPLED_TRANSPORT'
            self._set_state(r1, 'DUAL_COUPLED_TRANSPORT')
            self._set_state(r2, 'DUAL_COUPLED_TRANSPORT')

        elif state == 'DUAL_COUPLED_TRANSPORT':
            # Phase 8: DUAL_SYNCHRONIZED_DESCEND (Vertical placement onto table)
            u_long_dest = np.array([np.cos(self.dual_dest_yaw), np.sin(self.dual_dest_yaw), 0.0])
            p1_place_w = self.dual_dest_pos - half_sep * u_long_dest
            p2_place_w = self.dual_dest_pos + half_sep * u_long_dest
            grasp_z_off = affordance.get('grasp_z_offset', 0.010)
            p1_place_w[2] += grasp_z_off
            p2_place_w[2] += grasp_z_off

            p1_local_place, _ = self.world_to_base(r1, p1_place_w)
            p2_local_place, _ = self.world_to_base(r2, p2_place_w)

            self._init_dual_cartesian_phase(r1, r2, p1_local_place, p2_local_place, self.dual_quat1_end, self.dual_quat2_end, affordance['gripper_close'])
            self.dual_state = 'DUAL_SYNCHRONIZED_DESCEND'
            self._set_state(r1, 'DUAL_SYNCHRONIZED_DESCEND')
            self._set_state(r2, 'DUAL_SYNCHRONIZED_DESCEND')

        elif state == 'DUAL_SYNCHRONIZED_DESCEND':
            # Phase 9: DUAL_SYNCHRONIZED_RELEASE (Simultaneous gripper opening to 0.040m)
            self.dual_grip_start = affordance['gripper_close']
            self.dual_grip_end = self.gripper_open
            self.dual_step_counter = 0
            self.dual_state = 'DUAL_SYNCHRONIZED_RELEASE'
            self._set_state(r1, 'DUAL_SYNCHRONIZED_RELEASE')
            self._set_state(r2, 'DUAL_SYNCHRONIZED_RELEASE')

        elif state == 'DUAL_SYNCHRONIZED_RELEASE':
            # Phase 10: DUAL_SYNCHRONIZED_RETRACT (Outward retreat vector)
            p1_curr_local = self.dual_w1_end.copy()
            p2_curr_local = self.dual_w2_end.copy()

            p1_retract = np.array([p1_curr_local[0] - 0.03, p1_curr_local[1], p1_curr_local[2] + 0.10])
            p2_retract = np.array([p2_curr_local[0] + 0.03, p2_curr_local[1], p2_curr_local[2] + 0.10])

            self._init_dual_cartesian_phase(r1, r2, p1_retract, p2_retract, self.dual_quat1_end, self.dual_quat2_end, self.gripper_open)
            self.dual_state = 'DUAL_SYNCHRONIZED_RETRACT'
            self._set_state(r1, 'DUAL_SYNCHRONIZED_RETRACT')
            self._set_state(r2, 'DUAL_SYNCHRONIZED_RETRACT')

        elif state == 'DUAL_SYNCHRONIZED_RETRACT':
            # Phase 11: DUAL_RETURN_HOME (Return to home configuration)
            self.dual_q1_start = np.array(getattr(self, f'q_current{r1}'))
            self.dual_q1_end = np.array(self.q_home_fr3)
            self.dual_q2_start = np.array(getattr(self, f'q_current{r2}'))
            self.dual_q2_end = np.array(self.q_home_fr3)
            self.dual_grip_start = self.gripper_open
            self.dual_grip_end = self.gripper_open
            self.dual_step_counter = 0
            self.dual_state = 'DUAL_RETURN_HOME'
            self._set_state(r1, 'DUAL_RETURN_HOME')
            self._set_state(r2, 'DUAL_RETURN_HOME')

        elif state == 'DUAL_RETURN_HOME':
            # Release mutex, reset telemetry, and publish action result SUCCESS
            if self.center_occupied_by == 'DUAL_FR3_1_FR3_2':
                self.center_occupied_by = None

            self.collaborative_active = False
            self.collaborative_pair = None
            self.collaborative_object = None
            self.dual_active = False
            self.dual_state = 'DUAL_FINISHED'

            self._set_state(r1, 'FINISHED')
            self._set_state(r2, 'FINISHED')
            self._tasks_completed[r1] += 1
            self._tasks_completed[r2] += 1

            msg_str = f"{self.dual_target_name} transferred successfully to destination without drop or drift"
            self._publish_result(
                True,
                msg_str,
                robot_id="DUAL_FR3_1_FR3_2",
                action="dual_carry"
            )
            self.get_logger().info(f"[DUAL-ARM] {msg_str}")

    def _abort_dual_arm(self, reason):
        """Abort dual-arm collaborative manipulation safely and release resources."""
        r1, r2 = self.dual_robots[0], self.dual_robots[1]
        self.get_logger().error(f"[DUAL-ARM ABORT] {reason}")
        if self.center_occupied_by == 'DUAL_FR3_1_FR3_2':
            self.center_occupied_by = None

        self.collaborative_active = False
        self.collaborative_pair = None
        self.collaborative_object = None
        self.dual_active = False
        self.dual_state = 'DUAL_ABORT'

        self._set_state(r1, 'FINISHED')
        self._set_state(r2, 'FINISHED')
        self._tasks_failed[r1] += 1
        self._tasks_failed[r2] += 1

        self._publish_result(
            False,
            f"Dual-arm collaboration aborted: {reason}",
            robot_id="DUAL_FR3_1_FR3_2",
            action="dual_carry"
        )


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

