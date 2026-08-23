import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Empty
from rclpy.duration import Duration
import tf2_ros
import math
import numpy as np

try:
    from . import kinematics
except ImportError:
    import kinematics

class FrankaWslController(Node):
    def __init__(self):
        super().__init__('franka_wsl_controller')
        
        # Publisher to command joint positions
        self.cmd_pub = self.create_publisher(
            JointState, 
            '/isaac_joint_commands', 
            10
        )
        
        # Subscriber to read current joint positions from simulator
        self.state_sub = self.create_subscription(
            JointState,
            '/isaac_joint_states',
            self.state_callback,
            10
        )
        
        # Reset subscriber
        self.reset_sub = self.create_subscription(
            Empty, 
            '/reset_simulation', 
            self.reset_callback, 
            10
        )
        
        # TF Buffer & Listener
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        
        # Timer to publish commands at 50 Hz (0.02 second intervals)
        self.timer = self.create_timer(0.02, self.timer_callback)
        self.current_joints = None
        
        # Franka FR3 joint names
        self.joint_names = [
            "fr3_joint1", "fr3_joint2", "fr3_joint3", "fr3_joint4",
            "fr3_joint5", "fr3_joint6", "fr3_joint7",
            "fr3_finger_joint1", "fr3_finger_joint2"
        ]
        
        self.q_home = [0.0, 0.0, 0.0, -1.57, 0.0, 1.57, 0.785]
        self.q_current = list(self.q_home)
        
        # Gripper definitions
        self.gripper_open = 0.04
        self.gripper_close = 0.015
        
        # State machine
        # 'INIT' -> 'HOVER_PICK' -> 'DESCEND_PICK' -> 'GRASP' -> 'LIFT' ->
        # 'HOVER_PLACE' -> 'DESCEND_PLACE' -> 'RELEASE' -> 'RETRACT' -> 'FINISHED'
        self.state = 'INIT'
        self.block_index = 0
        self.step_counter = 0
        self.steps_per_phase = 100
        
        self.start_pos = None
        self.end_pos = None
        self.start_gripper = self.gripper_open
        self.end_gripper = self.gripper_open
        
        # Stacking target place position (world frame)
        # We place them at (0.4, -0.6) in the world
        self.stack_pos_world = [0.4, -0.6]
        
        self.get_logger().info("Franka WSL Controller Node Started. Control signals will publish to /isaac_joint_commands.")

    def transform_point(self, transform, point):
        p = transform.transform.translation
        q = transform.transform.rotation
        R = np.array([
            [1 - 2*q.y**2 - 2*q.z**2, 2*q.x*q.y - 2*q.z*q.w, 2*q.x*q.z + 2*q.y*q.w],
            [2*q.x*q.y + 2*q.z*q.w, 1 - 2*q.x**2 - 2*q.z**2, 2*q.y*q.z - 2*q.x*q.w],
            [2*q.x*q.z - 2*q.y*q.w, 2*q.y*q.z + 2*q.x*q.w, 1 - 2*q.x**2 - 2*q.y**2]
        ])
        return R @ np.array(point) + np.array([p.x, p.y, p.z])

    def state_callback(self, msg):
        self.current_joints = msg.position
        for i in range(7):
            name = f"fr3_joint{i+1}"
            if name in msg.name:
                idx = msg.name.index(name)
                self.q_current[i] = msg.position[idx]

    def reset_callback(self, msg):
        self.get_logger().info("Resetting simulation controller state machine...")
        self.state = 'INIT'
        self.block_index = 0
        self.step_counter = 0
        self.q_current = list(self.q_home)
        self.current_joints = None

    def get_block_link0_pos(self):
        name = f"Block{self.block_index+1}"
        try:
            trans = self.tf_buffer.lookup_transform('fr3_link0', name, rclpy.time.Time(), timeout=Duration(seconds=0.1))
            p = trans.transform.translation
            self.get_logger().info(f"TF block {name} in link0: [{p.x:.3f}, {p.y:.3f}, {p.z:.3f}]")
            return np.array([p.x, p.y, p.z])
        except Exception as e:
            self.get_logger().warning(f"TF lookup failed for {name}: {e}. Using fallback.")
             # Fallback based on typical relative position when base is at (0, -0.64, 0) rotated 90 degrees around Z axis
            # Block 1 is at (0.4, -0.4), Block 2 at (0.4, -0.5), Block 3 at (0.4, -0.3)
            # x_base = y_world + 0.64, y_base = -x_world, z_base = 0.03525
            y_worlds = [-0.4, -0.5, -0.3]
            y_world = y_worlds[self.block_index]
            x_base = y_world + 0.64
            y_base = -0.4
            return np.array([x_base, y_base, 0.03525])

    def get_place_link0_pos(self):
        try:
            trans = self.tf_buffer.lookup_transform('fr3_link0', 'world', rclpy.time.Time(), timeout=Duration(seconds=0.1))
            p_world = [self.stack_pos_world[0], self.stack_pos_world[1], 0.03525 + self.block_index * 0.04]
            p_link0 = self.transform_point(trans, p_world)
            self.get_logger().info(f"Place target in link0: [{p_link0[0]:.3f}, {p_link0[1]:.3f}, {p_link0[2]:.3f}]")
            return p_link0
        except Exception as e:
            self.get_logger().warning(f"TF world-to-link0 failed: {e}. Using fallback.")
            # Fallback based on base at (0, -0.64, 0) rotated 90 degrees around Z axis
            # Place target is at (0.4, -0.6)
            # x_base = y_world + 0.64 = -0.6 + 0.64 = 0.04
            # y_base = -x_world = -0.4
            z_offset = 0.03525 + self.block_index * 0.04
            return np.array([0.04, -0.4, z_offset])

    def initialize_phase(self, end_pos, end_gripper):
        T_curr = kinematics.forward_kinematics(self.q_current)
        self.start_pos = T_curr[:3, 3]
        self.end_pos = end_pos
        self.start_gripper = self.gripper_open if self.step_counter == 0 else self.end_gripper
        self.end_gripper = end_gripper
        self.step_counter = 0

    def timer_callback(self):
        if self.current_joints is None:
            return
            
        target_quat = [0.0, 1.0, 0.0, 0.0]
        
        if self.state == 'INIT':
            # Initialize by hovering above the first block
            block_pos = self.get_block_link0_pos()
            target_pos = block_pos + np.array([0.0, 0.0, 0.12])
            self.initialize_phase(target_pos, self.gripper_open)
            self.state = 'HOVER_PICK'
            
        elif self.state in ['HOVER_PICK', 'DESCEND_PICK', 'GRASP', 'LIFT', 'HOVER_PLACE', 'DESCEND_PLACE', 'RELEASE', 'RETRACT']:
            self.step_counter += 1
            t = min(float(self.step_counter) / self.steps_per_phase, 1.0)
            
            pos_target = self.start_pos + t * (self.end_pos - self.start_pos)
            grip_target = self.start_gripper + t * (self.end_gripper - self.start_gripper)
            
            q_sol, success = kinematics.inverse_kinematics(pos_target, target_quat, self.q_current)
            
            cmd = JointState()
            cmd.header.stamp = self.get_clock().now().to_msg()
            cmd.name = self.joint_names
            cmd.position = list(q_sol) + [grip_target, grip_target]
            self.cmd_pub.publish(cmd)
            
            for i in range(7):
                self.q_current[i] = q_sol[i]
                
            if self.step_counter >= self.steps_per_phase:
                self.get_logger().info(f"Completed arm phase: {self.state}")
                
                if self.state == 'HOVER_PICK':
                    # Descend onto block
                    block_pos = self.get_block_link0_pos()
                    target_pos = block_pos + np.array([0.0, 0.0, 0.015])
                    self.initialize_phase(target_pos, self.gripper_open)
                    self.state = 'DESCEND_PICK'
                    
                elif self.state == 'DESCEND_PICK':
                    # Grasp block
                    self.initialize_phase(self.end_pos, self.gripper_close)
                    self.state = 'GRASP'
                    
                elif self.state == 'GRASP':
                    # Lift block
                    target_pos = self.end_pos + np.array([0.0, 0.0, 0.12])
                    self.initialize_phase(target_pos, self.gripper_close)
                    self.state = 'LIFT'
                    
                elif self.state == 'LIFT':
                    # Move to hover above place position
                    place_pos = self.get_place_link0_pos()
                    target_pos = place_pos + np.array([0.0, 0.0, 0.12])
                    self.initialize_phase(target_pos, self.gripper_close)
                    self.state = 'HOVER_PLACE'
                    
                elif self.state == 'HOVER_PLACE':
                    # Descend to place position
                    place_pos = self.get_place_link0_pos()
                    target_pos = place_pos + np.array([0.0, 0.0, 0.015])
                    self.initialize_phase(target_pos, self.gripper_close)
                    self.state = 'DESCEND_PLACE'
                    
                elif self.state == 'DESCEND_PLACE':
                    # Release block
                    self.initialize_phase(self.end_pos, self.gripper_open)
                    self.state = 'RELEASE'
                    
                elif self.state == 'RELEASE':
                    # Retract arm
                    target_pos = self.end_pos + np.array([0.0, 0.0, 0.12])
                    self.initialize_phase(target_pos, self.gripper_open)
                    self.state = 'RETRACT'
                    
                elif self.state == 'RETRACT':
                    # Check if we have more blocks to pick (index 0, 1, 2 total 3 blocks)
                    if self.block_index < 2:
                        self.block_index += 1
                        block_pos = self.get_block_link0_pos()
                        target_pos = block_pos + np.array([0.0, 0.0, 0.12])
                        self.initialize_phase(target_pos, self.gripper_open)
                        self.state = 'HOVER_PICK'
                    else:
                        self.state = 'FINISHED'
                        self.get_logger().info("ALL BLOCKS PICK AND PLACED SUCCESSFULY INTO A TOWER!")
                        
        elif self.state == 'FINISHED':
            # Keep publishing home/stop pose
            cmd = JointState()
            cmd.header.stamp = self.get_clock().now().to_msg()
            cmd.name = self.joint_names
            cmd.position = self.q_home + [self.gripper_open, self.gripper_open]
            self.cmd_pub.publish(cmd)

def main(args=None):
    rclpy.init(args=args)
    node = FrankaWslController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Shutting down controller node.")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
