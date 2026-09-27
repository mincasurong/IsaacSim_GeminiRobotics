import rclpy
from rclpy.node import Node
import time
import json
from std_msgs.msg import String

# Wait for MoveIt to be initialized later
try:
    from moveit.planning import MoveItPy
    from moveit.core.robot_state import RobotState
except ImportError:
    MoveItPy = None

class MoveItControllerNode(Node):
    def __init__(self):
        super().__init__('multi_robot_moveit_controller')
        
        self.get_logger().info("Initializing MoveIt 2 Python API...")
        if MoveItPy is None:
            self.get_logger().error("MoveItPy is not installed!")
            return
            
        # Initialize MoveItPy (it reads parameters from the node's namespace)
        self.moveit_py = MoveItPy(node_name='multi_robot_moveit_controller')
        self.arms = {
            1: self.moveit_py.get_planning_component('fr3_1_arm'),
            2: self.moveit_py.get_planning_component('fr3_2_arm'),
            3: self.moveit_py.get_planning_component('fr3_3_arm')
        }
        
        # Subscriptions from Gemini
        self.sub_cmd1 = self.create_subscription(String, '/fr3_1/gemini_action_cmd', lambda msg: self._action_cb(msg, 1), 10)
        self.sub_cmd2 = self.create_subscription(String, '/fr3_2/gemini_action_cmd', lambda msg: self._action_cb(msg, 2), 10)
        self.sub_cmd3 = self.create_subscription(String, '/fr3_3/gemini_action_cmd', lambda msg: self._action_cb(msg, 3), 10)
        
        # Publishers to Gemini
        self.pub_res1 = self.create_publisher(String, '/fr3_1/gemini_action_result', 10)
        self.pub_res2 = self.create_publisher(String, '/fr3_2/gemini_action_result', 10)
        self.pub_res3 = self.create_publisher(String, '/fr3_3/gemini_action_result', 10)
        
        self.get_logger().info("MoveIt Multi-Robot Controller Ready.")

    def _action_cb(self, msg, robot_id):
        try:
            cmd = json.loads(msg.data)
            action = cmd.get('action')
            if action == 'pick':
                self.get_logger().info(f"Robot {robot_id}: Planning pick to {cmd.get('target')}")
                # We would fetch target TF, set MoveIt goal, plan and execute here.
                # Stub for now.
                self._publish_result(robot_id, True, "MoveIt pick stub executed.")
            elif action == 'go_home':
                self.get_logger().info(f"Robot {robot_id}: Planning return to home.")
                arm = self.arms[robot_id]
                arm.set_start_state_to_current_state()
                arm.set_goal_state(configuration_name=f'fr3_{robot_id}_home')
                
                plan = arm.plan()
                if plan:
                    self.get_logger().info(f"Robot {robot_id}: Plan found, executing...")
                    arm.execute()
                    self._publish_result(robot_id, True, "Returned home via MoveIt.")
                else:
                    self.get_logger().error(f"Robot {robot_id}: Planning failed!")
                    self._publish_result(robot_id, False, "MoveIt planning failed.")
            else:
                self.get_logger().warn(f"Robot {robot_id}: Unknown action {action}")
        except Exception as e:
            self.get_logger().error(f"Action parse failed: {e}")

    def _publish_result(self, robot_id, success, message):
        msg = String()
        msg.data = json.dumps({'success': success, 'message': message})
        if robot_id == 1: self.pub_res1.publish(msg)
        elif robot_id == 2: self.pub_res2.publish(msg)
        elif robot_id == 3: self.pub_res3.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = MoveItControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
