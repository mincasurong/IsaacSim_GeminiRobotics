"""Conveyor Dual-Robot Gemini VLA Orchestrator Node.

Architectural Design (Clean SWE SOTA):
Subclasses GeminiRoboticsNode to eliminate 1000+ lines of duplicated code.
Inherits all core capabilities:
- VLA multi-agent cognitive loop (Gemini Robotics-ER 2 + Function Calling)
- Rule-based safety verifier & pre-execution guardrails
- Closed-loop visual error recovery and replanning
- Telemetry & KPI experiment logging

Specializes:
- Dual-robot base geometry: FR3_1 at (-0.7, 0.0) and FR3_2 at (0.7, 0.0)
- Goal prompt for conveyor manipulation and bimanual transport
"""

import numpy as np
import rclpy
from rclpy.executors import MultiThreadedExecutor

try:
    from isaac_ros2_control.gemini_robotics_node import GeminiRoboticsNode as BaseGeminiNode
except ImportError:
    try:
        from .gemini_robotics_node import GeminiRoboticsNode as BaseGeminiNode
    except ImportError:
        from gemini_robotics_node import GeminiRoboticsNode as BaseGeminiNode


class ConveyorGeminiNode(BaseGeminiNode):
    """Specialized Gemini Robotics node for dual-arm conveyor manipulation and bimanual tasks."""

    def __init__(self, node_name: str = 'conveyor_gemini_node'):
        super().__init__(node_name=node_name)

        # Dual-robot conveyor geometry in world frame
        self.robot_bases = {
            'FR3_1': np.array([-0.7, 0.0]),
            'FR3_2': np.array([0.7, 0.0]),
        }

        # Conveyor-specific goal prompt
        self.user_goal = (
            "Manipulate objects on the conveyor belt and target tables using dual Franka FR3 arms. "
            "For single objects, pick and place with the nearest arm (FR3_1 for X < 0, FR3_2 for X >= 0). "
            "For oversized objects (LongBar, HeavyEnginePart), use coordinated dual-arm primitives "
            "(dual_arm_pick, dual_arm_place)."
        )
        self.get_logger().info("ConveyorGeminiNode initialized with dual-arm workspace partition.")


# Backward-compatibility alias
GeminiRoboticsNode = ConveyorGeminiNode


def main(args=None):
    rclpy.init(args=args)
    node = ConveyorGeminiNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
