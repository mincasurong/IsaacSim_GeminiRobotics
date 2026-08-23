import rclpy
from rclpy.node import Node
import tf2_ros
import sys

class TFChecker(Node):
    def __init__(self):
        super().__init__('tf_checker')
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self.timer = self.create_timer(1.0, self.timer_callback)
        self.count = 0

    def timer_callback(self):
        self.count += 1
        print(f"\n--- TF Lookup Attempt {self.count} ---")
        success = True
        for i in range(1, 4):
            name = f"Block{i}"
            try:
                # Get latest transform (time=0)
                trans = self.tf_buffer.lookup_transform('world', name, rclpy.time.Time())
                p = trans.transform.translation
                r = trans.transform.rotation
                print(f"{name}: Translation=[{p.x:.5f}, {p.y:.5f}, {p.z:.5f}], Rotation=[{r.x:.5f}, {r.y:.5f}, {r.z:.5f}, {r.w:.5f}]")
            except Exception as e:
                print(f"Failed to lookup {name}: {e}")
                success = False
        
        if success or self.count >= 5:
            print("Finished.")
            sys.exit(0)

def main():
    rclpy.init()
    node = TFChecker()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
