import rclpy
from moveit.planning import MoveItPy
from geometry_msgs.msg import PoseStamped
rclpy.init()
m = MoveItPy(node_name='test_moveit_py')
arm = m.get_planning_component('fr3_1_arm')
p = PoseStamped()
p.header.frame_id = 'base'
arm.set_goal_state(pose_stamped_msg=p, pose_link='robot1_fr3_hand')
print('SUCCESS')
