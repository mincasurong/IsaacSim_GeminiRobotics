import rclpy
from rclpy.node import Node
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import TransformStamped
import math

class FakeTF(Node):
    def __init__(self):
        super().__init__('fake_tf')
        self.br = TransformBroadcaster(self)
        self.timer = self.create_timer(0.1, self.publish_tf)
        
    def publish_tf(self):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'robot1_fr3_link0'
        t.child_frame_id = 'block_blue'
        
        # Place block in front of robot 1
        t.transform.translation.x = 0.5
        t.transform.translation.y = 0.0
        t.transform.translation.z = 0.025
        
        t.transform.rotation.x = 0.0
        t.transform.rotation.y = 0.0
        t.transform.rotation.z = 0.0
        t.transform.rotation.w = 1.0
        
        self.br.sendTransform(t)

def main(args=None):
    rclpy.init(args=args)
    node = FakeTF()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    rclpy.shutdown()

if __name__ == '__main__':
    main()
