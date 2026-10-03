"""Conveyor Dual-Robot Controller for Isaac Sim.

Inherits from MultiRobotController to share the core motion planning and execution engine:
- Damped Least Squares IK with SVD pseudoinverse & null-space regularizer
- State-gated mutual exclusion (CENTER_WORKSPACE_STATES)
- Minimum-jerk quintic trajectory interpolation
- Robust physical grasp verification window (0.012m - 0.038m)
- Read-only verify_tower inspection (zero arm/gripper motion, no dropped blocks)
- Dynamic conveyor tracking and visual servoing velocity forward prediction
- Synchronous dual-arm coordinated circular motion (draw circle while holding bar)
"""

import json
import time
import numpy as np
import rclpy
from sensor_msgs.msg import JointState
from std_msgs.msg import String

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
        self.conveyor_speed = 0.15  # m/s along world X (local -Y in robot base frame)
        
        # Dual-arm circle trajectory state
        self.dual_circle_active = False
        self.dual_circle_step = 0
        self.dual_circle_total_steps = 100
        self.dual_circle_radius = 0.08
        self.dual_circle_plane = 'XY'
        self.dual_circle_start_p1 = None
        self.dual_circle_start_p2 = None
        self.dual_circle_start_q1 = None
        self.dual_circle_start_q2 = None

        self.get_logger().info("ConveyorDualController initialized (Conveyor Servoing + Dual-Arm Manipulation).")

    def _resolve_block_name(self, label):
        """Robust multi-format resolver supporting Conveyor items, LongBar, Engine parts, and Blocks."""
        if not label:
            return None
        l = str(label).lower().strip()
        if 'bar' in l or 'longbar' in l: return 'LongBar'
        if 'engine' in l or 'heavyengine' in l: return 'HeavyEnginePart'
        if 'red' in l or 'block1' in l or 'block 1' in l: return 'Block1'
        if 'green' in l or 'block2' in l or 'block 2' in l: return 'Block2'
        if 'blue' in l or 'block3' in l or 'block 3' in l: return 'Block3'
        if 'yellow' in l or 'block4' in l or 'block 4' in l: return 'Block4'
        if 'magenta' in l or 'block5' in l or 'block 5' in l: return 'Block5'
        if 'cyan' in l or 'block6' in l or 'block 6' in l: return 'Block6'
        if 'orange' in l or 'block7' in l or 'block 7' in l: return 'Block7'
        if 'purple' in l or 'block8' in l or 'block 8' in l: return 'Block8'
        if 'lime' in l or 'block9' in l or 'block 9' in l: return 'Block9'
        for i in range(10):
            if f'convitem{i}' in l or f'convitem {i}' in l or f'item{i}' in l or f'item {i}' in l:
                return f'ConvItem{i}'
        return label

    def _action_cb(self, msg):
        try:
            cmd = json.loads(msg.data)
            action = cmd.get('action', '')

            # ── 1. DUAL ARM PICK ──────────────────────────────────────────────
            if action == 'dual_arm_pick':
                target_label = cmd.get('target', '') or cmd.get('object_label', 'LongBar')
                block_name = self._resolve_block_name(target_label)
                if not block_name:
                    self._publish_result(False, f"Could not map target '{target_label}' to a block prim.", "global")
                    return

                speed = cmd.get('speed', 'fast')
                steps = 25 if speed == 'fast' else (70 if speed == 'slow' else 40)
                self._action_start_time['global'] = time.monotonic()
                
                # Default symmetric grasp offsets along the bar length
                off1 = float(cmd.get('offset_1', -0.25))
                off2 = float(cmd.get('offset_2', 0.25))

                for rid, offset_val in [(1, off1), (2, off2)]:
                    self._action_start_time[rid] = time.monotonic()
                    setattr(self, f'gemini_action{rid}', 'dual_arm_pick')
                    setattr(self, f'active_target{rid}', block_name)
                    setattr(self, f'grasp_offset{rid}', offset_val)
                    setattr(self, f'steps_per_phase{rid}', steps)
                    setattr(self, f'hover_height{rid}', 0.12)
                    self._set_state(rid, 'INIT')
                self.get_logger().info(f"[DUAL-ARM PICK] Dispatched FR3_1 (off={off1}) and FR3_2 (off={off2}) for '{block_name}'")
                return

            # ── 2. DUAL ARM DRAW CIRCLE / MOTION ──────────────────────────────
            elif action in ['dual_arm_circle', 'dual_arm_draw_circle', 'dual_arm_motion']:
                radius = float(cmd.get('radius', 0.08))
                cycles = int(cmd.get('cycles', 1))
                plane = str(cmd.get('plane', 'XY')).upper()
                speed = cmd.get('speed', 'fast')
                steps_per_cycle = 75 if speed == 'fast' else (150 if speed == 'slow' else 100)
                
                self.dual_circle_radius = radius
                self.dual_circle_plane = plane
                self.dual_circle_step = 0
                self.dual_circle_total_steps = steps_per_cycle * cycles
                
                # Capture current Cartesian EE poses
                p1_local = kinematics.forward_kinematics(self.q_current1)[:3, 3]
                p2_local = kinematics.forward_kinematics(self.q_current2)[:3, 3]
                
                # Base orientation for FR3_1 and FR3_2 (base yaw = 90 deg)
                # World = R_base * local + t_base
                # R_base for 90 deg Z: [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
                R_base = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
                t_base1 = np.array([-0.7, 0.0, 0.20])
                t_base2 = np.array([0.7, 0.0, 0.20])
                
                self.dual_circle_start_p1 = R_base @ p1_local + t_base1
                self.dual_circle_start_p2 = R_base @ p2_local + t_base2
                self.dual_circle_start_q1 = np.array(self.q_current1)
                self.dual_circle_start_q2 = np.array(self.q_current2)
                
                self.dual_circle_active = True
                self._action_start_time['global'] = time.monotonic()
                for rid in [1, 2]:
                    self._action_start_time[rid] = time.monotonic()
                    setattr(self, f'gemini_action{rid}', 'dual_arm_circle')
                    self._set_state(rid, 'DUAL_ARM_CIRCLE')
                    
                self.get_logger().info(f"[DUAL-ARM CIRCLE] Starting synchronous {plane} circular trajectory (R={radius}m, cycles={cycles}, total_steps={self.dual_circle_total_steps})")
                return

            # ── 3. DUAL ARM PLACE ─────────────────────────────────────────────
            elif action == 'dual_arm_place':
                speed = cmd.get('speed', 'fast')
                steps = 25 if speed == 'fast' else (70 if speed == 'slow' else 40)
                self._action_start_time['global'] = time.monotonic()
                tx = float(cmd.get('x', 0.0))
                ty = float(cmd.get('y', -0.25))

                for rid in [1, 2]:
                    self._action_start_time[rid] = time.monotonic()
                    setattr(self, f'gemini_action{rid}', 'dual_arm_place')
                    setattr(self, f'target_x{rid}', tx)
                    setattr(self, f'target_y{rid}', ty)
                    setattr(self, f'steps_per_phase{rid}', steps)
                    setattr(self, f'hover_height{rid}', 0.12)
                    self._set_state(rid, 'WAIT_FOR_CENTER')
                self.get_logger().info(f"[DUAL-ARM PLACE] Dispatched placement to ({tx}, {ty})")
                return

            # All standard actions (pick, place, go_home, verify_tower) are handled by base class
            super()._action_cb(msg)
        except Exception as e:
            self._publish_result(False, f"Action parsing failed: {e}")

    def get_block_local_pose(self, robot_id):
        """Retrieve block position and optimal grasp quaternion with dual-arm and conveyor item support."""
        is_dual_arm_target = getattr(self, f'gemini_action{robot_id}', None) == 'dual_arm_pick'
        name = self.get_target_block_name(robot_id)
        if not name:
            return None, None

        frame = self.get_robot_base_frame(robot_id)
        try:
            trans = self.tf_buffer.lookup_transform(frame, name, rclpy.time.Time())
            p = trans.transform.translation
            q = trans.transform.rotation

            # Block yaw in base frame
            block_yaw = np.arctan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            
            if is_dual_arm_target:
                # Apply dual-arm offset along bar orientation
                offset_dist = getattr(self, f'grasp_offset{robot_id}', -0.25 if robot_id == 1 else 0.25)
                p.x += offset_dist * np.cos(block_yaw)
                p.y += offset_dist * np.sin(block_yaw)
                arm_yaw = np.arctan2(p.y, p.x)
                target_quat = kinematics.compute_symmetric_grasp_quat(block_yaw + np.pi / 2.0, arm_yaw)
            else:
                arm_yaw = np.arctan2(p.y, p.x)
                target_quat = kinematics.compute_symmetric_grasp_quat(block_yaw, arm_yaw)

            return np.array([p.x, p.y, p.z]), target_quat
        except Exception as e:
            self.get_logger().error(f"TF lookup failed for {name} to {frame}: {e}", throttle_duration_sec=1.0)
            return None, None

    def _process_robot(self, robot_id):
        """Process robot state with dynamic conveyor visual servoing and dual-arm circular trajectory."""
        state = getattr(self, f'state{robot_id}')

        # ── Synchronous Dual-Arm Circular Trajectory Execution ─────────────
        if state == 'DUAL_ARM_CIRCLE' and self.dual_circle_active:
            if robot_id == 1:
                self.dual_circle_step += 1

            k = self.dual_circle_step
            N = self.dual_circle_total_steps
            R = self.dual_circle_radius

            # Progress angle theta from 0 to 2*pi*cycles
            theta = 2.0 * np.pi * (float(k) / (N / max(1, int(round(N / 75.0)))))

            # Smooth cyclic displacement (starts and finishes at [0, 0, 0])
            if self.dual_circle_plane == 'YZ':
                delta_w = np.array([0.0, R * np.sin(theta), R * (1.0 - np.cos(theta))])
            elif self.dual_circle_plane == 'XZ':
                delta_w = np.array([R * np.sin(theta), 0.0, R * (1.0 - np.cos(theta))])
            else: # 'XY' plane default
                delta_w = np.array([R * np.sin(theta), R * (1.0 - np.cos(theta)), 0.0])

            # Robot base transform: R_base for 90 deg Z
            R_base = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
            t_base = np.array([-0.7 if robot_id == 1 else 0.7, 0.0, 0.20])
            
            # Compute target position in robot local frame
            start_p_w = self.dual_circle_start_p1 if robot_id == 1 else self.dual_circle_start_p2
            target_p_w = start_p_w + delta_w
            target_p_local = R_base.T @ (target_p_w - t_base)
            
            # Downward orientation
            target_quat = [0.0, 1.0, 0.0, 0.0]
            q_cur = getattr(self, f'q_current{robot_id}')
            q_sol, _ = kinematics.inverse_kinematics(target_p_local, target_quat, q_cur)

            # Publish joint command holding gripper closed
            cmd_pub = self.cmd_pub1 if robot_id == 1 else self.cmd_pub2
            cmd = JointState()
            cmd.header.stamp = self.get_clock().now().to_msg()
            cmd.name = self.joint_names_fr3
            cmd.position = list(q_sol) + [self.gripper_close, self.gripper_close]
            cmd_pub.publish(cmd)

            # Update joint cache
            if robot_id == 1:
                for i in range(7): self.q_current1[i] = q_sol[i]
            else:
                for i in range(7): self.q_current2[i] = q_sol[i]

            # Check completion
            if k >= N:
                self.dual_circle_active = False
                self._set_state(1, 'WAITING_FOR_PLACE_CMD')
                self._set_state(2, 'WAITING_FOR_PLACE_CMD')
                self._publish_result(True, f"Dual-arm synchronized {self.dual_circle_plane} circular motion completed successfully.", "global")
                self.get_logger().info("[DUAL-ARM CIRCLE] Coordinated circular trajectory finished successfully.")
            return

        # ── Dynamic Conveyor Servoing: Track Moving Objects in Real-Time ────
        if self.conveyor_tracking and state in ['HOVER_PICK', 'DESCEND_PICK']:
            block_pos, _ = self.get_block_local_pose(robot_id)
            if block_pos is not None:
                # In robot base frame (yaw=90°), World +X motion corresponds to Local -Y
                # Predict forward lookahead based on phase duration
                lookahead_t = 0.15 if state == 'HOVER_PICK' else 0.08
                predicted_y = block_pos[1] - (self.conveyor_speed * lookahead_t)
                
                if state == 'HOVER_PICK':
                    end_pos = np.array([block_pos[0], predicted_y, block_pos[2] + self.hover_height])
                else:
                    end_pos = np.array([block_pos[0], predicted_y, block_pos[2]])
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
