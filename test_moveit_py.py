import rclpy
from rclpy.node import Node
from moveit.core.robot_state import RobotState
from moveit.planning import MoveItPy

rclpy.init()
node = Node('test_node')
node.get_logger().info('Hello')
try:
    moveit_py = MoveItPy(node_name='test_node')
    print('MoveItPy initialized')
except Exception as e:
    print(e)
finally:
    rclpy.shutdown()
