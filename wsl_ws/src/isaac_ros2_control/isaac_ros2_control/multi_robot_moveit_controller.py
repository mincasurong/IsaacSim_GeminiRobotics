import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
import time
import json
import threading
from std_msgs.msg import String
import tf2_ros
from geometry_msgs.msg import PoseStamped
import math

try:
    from moveit.planning import MoveItPy
    from moveit.core.robot_state import RobotState
except ImportError:
    MoveItPy = None

class MoveItControllerNode(Node):
    def __init__(self):
        super().__init__('multi_robot_moveit_controller', 
                         allow_undeclared_parameters=True, 
                         automatically_declare_parameters_from_overrides=True)
        
        self.get_logger().info("Initializing MoveIt 2 Python API...")
        if MoveItPy is None:
            self.get_logger().error("MoveItPy is not installed!")
            return
            
        self.moveit_py = MoveItPy(node_name='multi_robot_moveit_controller')
        self.arms = {
            1: self.moveit_py.get_planning_component('fr3_1_arm'),
            2: self.moveit_py.get_planning_component('fr3_2_arm'),
            3: self.moveit_py.get_planning_component('fr3_3_arm')
        }
        
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        
        self.tower_height = 0
        
        self.sub_cmd1 = self.create_subscription(String, '/fr3_1/gemini_action_cmd', lambda msg: self._action_cb(msg, 1), 10)
        self.sub_cmd2 = self.create_subscription(String, '/fr3_2/gemini_action_cmd', lambda msg: self._action_cb(msg, 2), 10)
        self.sub_cmd3 = self.create_subscription(String, '/fr3_3/gemini_action_cmd', lambda msg: self._action_cb(msg, 3), 10)
        
        self.pub_res1 = self.create_publisher(String, '/fr3_1/gemini_action_result', 10)
        self.pub_res2 = self.create_publisher(String, '/fr3_2/gemini_action_result', 10)
        self.pub_res3 = self.create_publisher(String, '/fr3_3/gemini_action_result', 10)
        
        self.pub_grip1 = self.create_publisher(String, '/fr3_1/gripper_cmd', 10)
        self.pub_grip2 = self.create_publisher(String, '/fr3_2/gripper_cmd', 10)
        self.pub_grip3 = self.create_publisher(String, '/fr3_3/gripper_cmd', 10)
        
        self.get_logger().info("MoveIt Multi-Robot Controller Ready.")

    def _action_cb(self, msg, robot_id):
        # Run action in a separate thread to avoid blocking ROS spinner
        threading.Thread(target=self._execute_action, args=(msg.data, robot_id)).start()

    def _execute_action(self, msg_data, robot_id):
        try:
            cmd = json.loads(msg_data)
            action = cmd.get('action')
            target = cmd.get('target', '')
            
            if action == 'pick':
                self.get_logger().info(f"Robot {robot_id}: Planning pick for {target}")
                self._execute_pick(robot_id, target)
            elif action == 'place':
                self.get_logger().info(f"Robot {robot_id}: Planning place to {target}")
                self._execute_place(robot_id, target)
            elif action == 'go_home':
                self.get_logger().info(f"Robot {robot_id}: Planning return to home.")
                arm = self.arms[robot_id]
                arm.set_start_state_to_current_state()
                arm.set_goal_state(configuration_name=f'fr3_{robot_id}_home')
                
                plan = arm.plan()
                if plan:
                    self.get_logger().info(f"Robot {robot_id}: Plan found, executing...")
                    self.moveit_py.execute(plan.trajectory, controllers=[])
                    self._publish_result(robot_id, True, "Returned home via MoveIt.")
                else:
                    self.get_logger().error(f"Robot {robot_id}: Planning failed!")
                    self._publish_result(robot_id, False, "MoveIt planning failed.")
            elif action == 'reset':
                self.tower_height = 0
                self._publish_result(robot_id, True, "Reset completed.")
            else:
                self.get_logger().warn(f"Robot {robot_id}: Unknown action {action}")
        except Exception as e:
            self.get_logger().error(f"Action parse failed: {e}")

    def _get_tf_pose(self, target_frame, robot_id):
        try:
            # Wait a bit for transform if necessary
            tf = self.tf_buffer.lookup_transform(f'robot{robot_id}_fr3_link0', target_frame, rclpy.time.Time(), rclpy.duration.Duration(seconds=1.0))
            return tf.transform.translation
        except Exception as e:
            self.get_logger().error(f"TF lookup failed for {target_frame}: {e}")
            return None

    def _move_to_pose(self, robot_id, x, y, z):
        arm = self.arms[robot_id]
        arm.set_start_state_to_current_state()

        pose = PoseStamped()
        pose.header.frame_id = f'robot{robot_id}_fr3_link0'
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = z
        
        # Explicit downward-facing quaternion for FR3 (180 deg around X-axis of link0)
        # This points the gripper Z-axis downward (-Z of base)
        pose.pose.orientation.x = 1.0
        pose.pose.orientation.y = 0.0
        pose.pose.orientation.z = 0.0
        pose.pose.orientation.w = 0.0

        # Set goal state
        arm.set_goal_state(pose_stamped_msg=pose, pose_link=f"robot{robot_id}_fr3_hand")
        plan = arm.plan()

        if plan:
            self.moveit_py.execute(plan.trajectory, controllers=[])
            return True
        else:
            self.get_logger().error(f"Robot {robot_id}: Planning failed to pose ({x}, {y}, {z})")
            return False

    def _set_gripper(self, robot_id, action):
        msg = String()
        msg.data = action
        if robot_id == 1: self.pub_grip1.publish(msg)
        elif robot_id == 2: self.pub_grip2.publish(msg)
        elif robot_id == 3: self.pub_grip3.publish(msg)
        time.sleep(0.5)

    def _execute_pick(self, robot_id, target):
        trans = self._get_tf_pose(target, robot_id)
        if not trans:
            self._publish_result(robot_id, False, f"Could not find {target}")
            return
            
        # Approach
        if not self._move_to_pose(robot_id, trans.x, trans.y, trans.z + 0.3):
            self._publish_result(robot_id, False, "Pick approach failed")
            return
            
        # Descend
        if not self._move_to_pose(robot_id, trans.x, trans.y, trans.z + 0.15):
            self._publish_result(robot_id, False, "Pick descend failed")
            return
            
        # Grasp
        self._set_gripper(robot_id, "close")
        
        # Lift
        if not self._move_to_pose(robot_id, trans.x, trans.y, trans.z + 0.3):
            self._publish_result(robot_id, False, "Pick lift failed")
            return
            
        self._publish_result(robot_id, True, f"Pick completed for {target}")

    def _execute_place(self, robot_id, target):
        trans = self._get_tf_pose(target, robot_id)
        if not trans:
            self._publish_result(robot_id, False, f"Could not find {target}")
            return
            
        place_z = trans.z + (self.tower_height * 0.051) + 0.1
        
        # Approach
        if not self._move_to_pose(robot_id, trans.x, trans.y, place_z + 0.2):
            self._publish_result(robot_id, False, "Place approach failed")
            return
            
        # Descend
        if not self._move_to_pose(robot_id, trans.x, trans.y, place_z + 0.15):
            self._publish_result(robot_id, False, "Place descend failed")
            return
            
        # Release
        self._set_gripper(robot_id, "open")
        
        # Lift
        if not self._move_to_pose(robot_id, trans.x, trans.y, place_z + 0.2):
            self._publish_result(robot_id, False, "Place lift failed")
            return
            
        self.tower_height += 1
        self._publish_result(robot_id, True, f"Place completed. Tower height is now {self.tower_height}")

    def _publish_result(self, robot_id, success, message):
        msg = String()
        msg.data = json.dumps({'success': success, 'message': message})
        if robot_id == 1: self.pub_res1.publish(msg)
        elif robot_id == 2: self.pub_res2.publish(msg)
        elif robot_id == 3: self.pub_res3.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    controller = MoveItControllerNode()
    executor = MultiThreadedExecutor()
    executor.add_node(controller)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        controller.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
