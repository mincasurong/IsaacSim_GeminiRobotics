"""Conveyor Dual-Robot Controller for Isaac Sim.

Inherits from MultiRobotController to share the core motion planning and execution engine:
- Damped Least Squares IK with SVD pseudoinverse & null-space regularizer
- State-gated mutual exclusion (CENTER_WORKSPACE_STATES)
- Minimum-jerk quintic trajectory interpolation
- Robust physical grasp verification window (0.005m - 0.038m)
- Read-only verify_tower inspection (zero arm/gripper motion, no dropped blocks)
- 300ms (15 steps) gripper actuation dwell
"""

import json
import time
import numpy as np
import rclpy

try:
    from isaac_ros2_control.multi_robot_controller import (
        MultiRobotController,
        CENTER_WORKSPACE_STATES,
    )
    from isaac_ros2_control import kinematics
except ImportError:
    try:
        from .multi_robot_controller import (
            MultiRobotController,
            CENTER_WORKSPACE_STATES,
        )
        from . import kinematics
    except ImportError:
        from multi_robot_controller import (
            MultiRobotController,
            CENTER_WORKSPACE_STATES,
        )
        import kinematics


class ConveyorDualController(MultiRobotController):
    """Dual FR3 Controller extending the shared MultiRobotController engine."""

    def __init__(self):
        super().__init__(node_name='conveyor_dual_controller')
        # Dual-arm setup: only FR3_1 and FR3_2 are active on the conveyor
        self.active_robot_ids = [1, 2]
        self.conveyor_tracking = True
        self.conveyor_speed = 0.15  # m/s along world X (local -Y in robot frame)

    def _action_cb(self, msg):
        try:
            cmd = json.loads(msg.data)
            action = cmd.get('action', '')

            if action == 'dual_arm_pick':
                target_label = cmd.get('target', '')
                block_name = self._resolve_block_name(target_label)
                if not block_name:
                    self._publish_result(False, f"Could not map target '{target_label}' to a block prim.", "global")
                    return
                # Setup both robots for coordinated grasp
                speed = cmd.get('speed', 'fast')
                steps = 20 if speed == 'fast' else (70 if speed == 'slow' else 40)
                self._action_start_time['global'] = time.monotonic()
                for rid, offset_key in [(1, 'offset_1'), (2, 'offset_2')]:
                    self._action_start_time[rid] = time.monotonic()
                    setattr(self, f'gemini_action{rid}', 'dual_arm_pick')
                    setattr(self, f'active_target{rid}', block_name)
                    setattr(self, f'grasp_offset{rid}', float(cmd.get(offset_key, 0.0)))
                    setattr(self, f'steps_per_phase{rid}', steps)
                    setattr(self, f'hover_height{rid}', 0.10)
                    self._set_state(rid, 'INIT')
                return

            elif action == 'dual_arm_place':
                speed = cmd.get('speed', 'fast')
                steps = 20 if speed == 'fast' else (70 if speed == 'slow' else 40)
                self._action_start_time['global'] = time.monotonic()
                for rid in [1, 2]:
                    self._action_start_time[rid] = time.monotonic()
                    setattr(self, f'gemini_action{rid}', 'dual_arm_place')
                    setattr(self, f'target_x{rid}', cmd.get('x', 0.0))
                    setattr(self, f'target_y{rid}', cmd.get('y', 0.0))
                    setattr(self, f'steps_per_phase{rid}', steps)
                    setattr(self, f'hover_height{rid}', 0.10)
                    curr_state = getattr(self, f'state{rid}')
                    if curr_state == 'WAITING_FOR_PLACE_CMD':
                        self._set_state(rid, 'WAIT_FOR_CENTER')
                    else:
                        self._publish_result(False, f"Robot {rid} is not ready to place (in {curr_state}).", f"FR3_{rid}")
                return

            # All standard actions (pick, place, go_home, verify_tower) are handled by the robust base class!
            # verify_tower in base class is READ-ONLY and will never drop held objects or open grippers.
            super()._action_cb(msg)
        except Exception as e:
            self._publish_result(False, f"Action parsing failed: {e}")

    def get_block_local_pose(self, robot_id):
        """Retrieve block position and optimal grasp quaternion, with dual-arm support."""
        is_dual_arm_target = getattr(self, f'gemini_action{robot_id}', None) == 'dual_arm_pick'
        if not is_dual_arm_target:
            return super().get_block_local_pose(robot_id)

        name = self.get_target_block_name(robot_id)
        if not name:
            return None, None

        frame = self.get_robot_base_frame(robot_id)
        try:
            trans = self.tf_buffer.lookup_transform(
                frame, name, rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=0.05)
            )
            p = trans.transform.translation
            q = trans.transform.rotation

            # Block yaw in base frame
            block_yaw = np.arctan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))

            # Retrieve dynamically reasoned offset from the VLA tool call
            offset_dist = getattr(self, f'grasp_offset{robot_id}', -0.3 if robot_id == 1 else 0.3)
            p.x += offset_dist * np.cos(block_yaw)
            p.y += offset_dist * np.sin(block_yaw)

            arm_yaw = np.arctan2(p.y, p.x)
            target_quat = kinematics.compute_symmetric_grasp_quat(block_yaw + np.pi / 2.0, arm_yaw)

            return np.array([p.x, p.y, p.z]), target_quat
        except Exception as e:
            self.get_logger().error(f"TF lookup failed for {name} to {frame}: {e}", throttle_duration_sec=1.0)
            return None, None

    def _process_robot(self, robot_id):
        """Process robot state with dynamic conveyor prediction before base execution."""
        state = getattr(self, f'state{robot_id}')
        # DYNAMIC TRACKING: If picking on moving conveyor, continuously update target position
        if self.conveyor_tracking and state in ['HOVER_PICK', 'DESCEND_PICK']:
            block_pos, _ = self.get_block_local_pose(robot_id)
            if block_pos is not None:
                # Forward prediction: world X velocity 0.15m/s -> local -Y velocity
                block_pos[1] -= (self.conveyor_speed * 0.15)
                if state == 'HOVER_PICK':
                    end_pos = np.array([block_pos[0], block_pos[1], block_pos[2] + self.hover_height])
                else:
                    end_pos = np.array([block_pos[0], block_pos[1], block_pos[2] - 0.02])
                setattr(self, f'end_pos{robot_id}', end_pos)

        super()._process_robot(robot_id)


def main(args=None):
    rclpy.init(args=args)
    node = ConveyorDualController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
