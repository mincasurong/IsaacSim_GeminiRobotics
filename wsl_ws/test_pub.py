#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

def main(args=None):
    rclpy.init(args=args)
    node = Node('test_publisher')
    pub = node.create_publisher(String, '/fr3_1/gemini_action_cmd', 10)
    
    msg = String()
    msg.data = '{"action": "pick", "target": "block_blue"}'
    
    # Wait for subscribers
    import time
    time.sleep(3)
    
    node.get_logger().info('Publishing go_home...')
    pub.publish(msg)
    time.sleep(1)
    
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
