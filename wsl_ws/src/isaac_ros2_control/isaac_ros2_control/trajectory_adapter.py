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
            
            # Subscribe to individual joint states
            self.create_subscription(JointState, f'/fr3_{i}/joint_states', lambda msg, r_id=i: self.js_cb(msg, r_id), 10)
            
            self.get_logger().info(f'Action server up: /fr3_{i}_arm_controller/follow_joint_trajectory')

        # Global joint states publisher
        self.js_pub = self.create_publisher(JointState, '/joint_states', 10)
        self.js_cache = {}
        
        # Initialize with zeros to satisfy MoveIt2 startup
        for i in range(1, 4):
            msg = JointState()
            msg.name = [
                f'robot{i}_fr3_joint1', f'robot{i}_fr3_joint2', f'robot{i}_fr3_joint3',
                f'robot{i}_fr3_joint4', f'robot{i}_fr3_joint5', f'robot{i}_fr3_joint6',
                f'robot{i}_fr3_joint7', f'robot{i}_fr3_finger_joint1', f'robot{i}_fr3_finger_joint2'
            ]
            msg.position = [
                0.0, -0.7854, 0.0, -2.3562, 0.0, 1.5708, 0.7854,
                0.04, 0.04
            ]
            self.js_cache[i] = msg
            
        self.create_timer(0.02, self.publish_global_js)

    def js_cb(self, msg, robot_id):
        # The Isaac Sim msg might not have prefixes, so add them
        names = []
        for n in msg.name:
            if n.startswith('fr3_'):
                names.append(n.replace('fr3_', f'robot{robot_id}_fr3_'))
            else:
                names.append(f'robot{robot_id}_fr3_{n}')
        msg.name = names
        self.js_cache[robot_id] = msg

    def publish_global_js(self):
        if not self.js_cache:
            return
            
        out_msg = JointState()
        out_msg.header.stamp = self.get_clock().now().to_msg()
        for r_id, msg in self.js_cache.items():
            out_msg.name.extend(msg.name)
            out_msg.position.extend(msg.position)
            if msg.velocity:
                out_msg.velocity.extend(msg.velocity)
            if msg.effort:
                out_msg.effort.extend(msg.effort)
                
        self.js_pub.publish(out_msg)

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
                isaac_joint_names = [n.replace(f'robot{robot_id}_fr3_', '') for n in joint_names]
                msg = JointState()
                msg.header.stamp = now.to_msg()
                msg.name = isaac_joint_names
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
            
            # Strip prefix for Isaac Sim
            isaac_joint_names = [n.replace(f'robot{robot_id}_fr3_', '') for n in joint_names]
            
            msg = JointState()
            msg.header.stamp = now.to_msg()
            msg.name = isaac_joint_names
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
