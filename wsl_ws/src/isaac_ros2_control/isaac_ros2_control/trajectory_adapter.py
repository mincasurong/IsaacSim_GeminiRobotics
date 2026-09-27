import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer
from control_msgs.action import FollowJointTrajectory
from sensor_msgs.msg import JointState
import numpy as np

class TrajectoryAdapter(Node):
    """
    Subscribes to MoveIt 2 FollowJointTrajectory action and publishes 50Hz JointState commands
    to Isaac Sim's ROS2SubscribeJointState nodes.
    """
    def __init__(self):
        super().__init__('trajectory_adapter')
        
        # We need three action servers and three publishers
        self.action_servers = []
        self.publishers_map = {}
        
        for i in range(1, 4):
            pub = self.create_publisher(JointState, f'/fr3_{i}/joint_commands', 10)
            self.publishers_map[i] = pub
            
            action_server = ActionServer(
                self,
                FollowJointTrajectory,
                f'/fr3_{i}_arm_controller/follow_joint_trajectory',
                lambda goal_handle, r_id=i: self.execute_callback(goal_handle, r_id)
            )
            self.action_servers.append(action_server)
            self.get_logger().info(f'Action server up: /fr3_{i}_arm_controller/follow_joint_trajectory')

    def execute_callback(self, goal_handle, robot_id):
        self.get_logger().info(f'Robot {robot_id}: Received trajectory goal.')
        
        trajectory = goal_handle.request.trajectory
        points = trajectory.points
        joint_names = trajectory.joint_names
        
        if not points:
            goal_handle.succeed()
            return FollowJointTrajectory.Result(error_code=FollowJointTrajectory.Result.SUCCESSFUL)
            
        pub = self.publishers_map[robot_id]
        
        # 50Hz interpolation loop (0.02s dt)
        start_time = self.get_clock().now()
        
        dt = 0.02
        current_idx = 0
        
        while current_idx < len(points):
            now = self.get_clock().now()
            elapsed_sec = (now - start_time).nanoseconds / 1e9
            
            # Find the segment we are in
            while current_idx < len(points) - 1:
                pt_time = points[current_idx+1].time_from_start.sec + points[current_idx+1].time_from_start.nanosec / 1e9
                if elapsed_sec < pt_time:
                    break
                current_idx += 1
                
            if current_idx >= len(points) - 1:
                # We reached the end
                pt = points[-1]
                msg = JointState()
                msg.header.stamp = now.to_msg()
                msg.name = joint_names
                msg.position = pt.positions
                pub.publish(msg)
                break
                
            # Interpolate
            pt0 = points[current_idx]
            pt1 = points[current_idx+1]
            
            t0 = pt0.time_from_start.sec + pt0.time_from_start.nanosec / 1e9
            t1 = pt1.time_from_start.sec + pt1.time_from_start.nanosec / 1e9
            
            if t1 > t0:
                alpha = (elapsed_sec - t0) / (t1 - t0)
                alpha = max(0.0, min(1.0, alpha))
            else:
                alpha = 1.0
                
            pos0 = np.array(pt0.positions)
            pos1 = np.array(pt1.positions)
            interp_pos = pos0 + alpha * (pos1 - pos0)
            
            msg = JointState()
            msg.header.stamp = now.to_msg()
            msg.name = joint_names
            msg.position = interp_pos.tolist()
            pub.publish(msg)
            
            # Sleep until next 50Hz tick
            import time
            time.sleep(dt)
            
        goal_handle.succeed()
        self.get_logger().info(f'Robot {robot_id}: Trajectory finished.')
        
        result = FollowJointTrajectory.Result()
        result.error_code = FollowJointTrajectory.Result.SUCCESSFUL
        return result

def main(args=None):
    rclpy.init(args=args)
    node = TrajectoryAdapter()
    # Use MultiThreadedExecutor if we want concurrent arm movements
    from rclpy.executors import MultiThreadedExecutor
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
