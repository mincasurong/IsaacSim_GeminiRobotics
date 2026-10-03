import re

with open('/mnt/d/git/IsaacSim_Gemini/wsl_ws/src/isaac_ros2_control/isaac_ros2_control/gemini_robotics_node.py', 'r') as f:
    code = f.read()

replacement = '''    def _custom_goal_callback(self, msg):
        import time
        now = time.time()
        if hasattr(self, '_last_goal_time') and (now - self._last_goal_time < 2.0):
            self.get_logger().info(" Ignoring duplicate goal command received within 2 seconds.)
