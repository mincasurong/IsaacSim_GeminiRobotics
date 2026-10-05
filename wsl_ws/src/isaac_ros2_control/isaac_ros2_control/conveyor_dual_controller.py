"""Conveyor Dual-Robot Controller for Isaac Sim.

SOLID Architecture (SOTA October 2026):
- Single Responsibility:
  * DualArmCircleTrajectory: Computes parametric closed-chain SE(3) circle trajectories.
  * DualArmPlaceTrajectory: Computes quintic polynomial synchronized Cartesian placement.
  * ConveyorDualController: Orchestrates robot states, visual servoing, and ROS 2 command loops.
- Liskov Substitution:
  * Seamlessly substitutes MultiRobotController while preserving all ROS 2 topic/action interfaces.
- Open/Closed:
  * New collaborative dual-arm primitives can be added as trajectory strategies without altering core control loop.
"""

import json
import time
from typing import Dict, Any, Tuple, Optional
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


# Shared Base Orientation Matrix (Yaw = 90 deg: +X_local -> +Y_world, +Y_local -> -X_world)
R_BASE_90 = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]], dtype=float)
T_BASE1 = np.array([-0.7, 0.0, 0.20], dtype=float)
T_BASE2 = np.array([0.7, 0.0, 0.20], dtype=float)


class DualArmCircleTrajectory:
    """Computes closed-chain parametric SE(3) circular trajectories."""

    def __init__(self, radius: float = 0.08, cycles: int = 1, plane: str = 'XY', steps_per_cycle: int = 75):
        self.radius = radius
        self.cycles = cycles
        self.plane = plane.upper()
        self.steps_per_cycle = steps_per_cycle
        self.total_steps = steps_per_cycle * cycles
        self.current_step = 0
        self.start_p1_w: Optional[np.ndarray] = None
        self.start_p2_w: Optional[np.ndarray] = None
        self.start_quat1: Optional[np.ndarray] = None
        self.start_quat2: Optional[np.ndarray] = None

    def initialize(self, q1: list, q2: list):
        """Capture initial world-frame end-effector positions and orientations."""
        p1_local = kinematics.forward_kinematics(q1)[:3, 3]
        p2_local = kinematics.forward_kinematics(q2)[:3, 3]

        self.start_p1_w = R_BASE_90 @ p1_local + T_BASE1
        self.start_p2_w = R_BASE_90 @ p2_local + T_BASE2

        T1 = kinematics.forward_kinematics(q1)
        self.start_quat1 = kinematics.rot_matrix_to_quat(T1[:3, :3])
        T2 = kinematics.forward_kinematics(q2)
        self.start_quat2 = kinematics.rot_matrix_to_quat(T2[:3, :3])

        self.current_step = 0

    def step(self, robot_id: int, q_current: list) -> Tuple[np.ndarray, bool]:
        """Compute next joint solution for robot along the circle trajectory."""
        if robot_id == 1:
            self.current_step += 1

        k = self.current_step
        theta = 2.0 * np.pi * (float(k) / float(self.steps_per_cycle))
        R = self.radius

        if self.plane == 'YZ':
            delta_w = np.array([0.0, R * np.sin(theta), R * (1.0 - np.cos(theta))])
        elif self.plane == 'XZ':
            delta_w = np.array([R * np.sin(theta), 0.0, R * (1.0 - np.cos(theta))])
        else:  # 'XY'
            delta_w = np.array([R * np.sin(theta), R * (1.0 - np.cos(theta)), 0.0])

        t_base = T_BASE1 if robot_id == 1 else T_BASE2
        start_p_w = self.start_p1_w if robot_id == 1 else self.start_p2_w
        target_p_w = start_p_w + delta_w
        target_p_local = R_BASE_90.T @ (target_p_w - t_base)

        target_quat = self.start_quat1 if robot_id == 1 else self.start_quat2
        q_sol, _ = kinematics.inverse_kinematics(target_p_local, target_quat, q_current)

        is_finished = (k >= self.total_steps)
        return q_sol, is_finished


class DualArmPlaceTrajectory:
    """Computes synchronized quintic polynomial placement with release & retract phases."""

    def __init__(self, target_x: float = 0.0, target_y: float = 0.25, total_steps: int = 35):
        self.target_x = target_x
        self.target_y = target_y
        self.total_steps = total_steps
        self.step1 = 0
        self.step2 = 0
        self.phase = 'DESCEND'  # 'DESCEND' -> 'RELEASE' -> 'RETRACT'
        self.start_p1_w: Optional[np.ndarray] = None
        self.start_p2_w: Optional[np.ndarray] = None
        self.target_p1_w = np.array([target_x - 0.25, target_y, 0.35], dtype=float)
        self.target_p2_w = np.array([target_x + 0.25, target_y, 0.35], dtype=float)
        self.grasp_quat1: Optional[np.ndarray] = None
        self.grasp_quat2: Optional[np.ndarray] = None

    def initialize(self, q1: list, q2: list):
        """Capture starting world poses before descent."""
        p1_local = kinematics.forward_kinematics(q1)[:3, 3]
        p2_local = kinematics.forward_kinematics(q2)[:3, 3]

        self.start_p1_w = R_BASE_90 @ p1_local + T_BASE1
        self.start_p2_w = R_BASE_90 @ p2_local + T_BASE2

        T1 = kinematics.forward_kinematics(q1)
        self.grasp_quat1 = kinematics.rot_matrix_to_quat(T1[:3, :3])
        T2 = kinematics.forward_kinematics(q2)
        self.grasp_quat2 = kinematics.rot_matrix_to_quat(T2[:3, :3])

        self.step1 = 0
        self.step2 = 0
        self.phase = 'DESCEND'

    def step(self, robot_id: int, q_current: list, gripper_open: float, gripper_close: float) -> Tuple[np.ndarray, float, bool]:
        """Compute next joint solution and gripper target for placement phase."""
        t_base = T_BASE1 if robot_id == 1 else T_BASE2
        grasp_quat = self.grasp_quat1 if robot_id == 1 else self.grasp_quat2

        if robot_id == 1:
            self.step1 += 1
            k = self.step1
        else:
            self.step2 += 1
            k = self.step2

        if self.phase == 'DESCEND':
            t = min(float(k) / float(self.total_steps), 1.0)
            t_smooth = 10 * (t ** 3) - 15 * (t ** 4) + 6 * (t ** 5)

            p_start = self.start_p1_w if robot_id == 1 else self.start_p2_w
            p_target = self.target_p1_w if robot_id == 1 else self.target_p2_w

            target_p_w = p_start + t_smooth * (p_target - p_start)
            target_p_local = R_BASE_90.T @ (target_p_w - t_base)

            q_sol, _ = kinematics.inverse_kinematics(target_p_local, grasp_quat, q_current)
            grip_val = gripper_close

            # Phase transition occurs only after both arms finish descent
            if self.step1 >= self.total_steps and self.step2 >= self.total_steps:
                self.phase = 'RELEASE'
                self.step1 = 0
                self.step2 = 0

            return q_sol, grip_val, False

        elif self.phase == 'RELEASE':
            q_sol = np.array(q_current)
            grip_val = gripper_open
            # Dwell 20 steps (400ms) with fingers open so bar rests safely
            if self.step1 >= 20 and self.step2 >= 20:
                self.phase = 'RETRACT'
                self.step1 = 0
                self.step2 = 0
            return q_sol, grip_val, False

        elif self.phase == 'RETRACT':
            t = min(float(k) / float(30), 1.0)
            t_smooth = 10 * (t ** 3) - 15 * (t ** 4) + 6 * (t ** 5)

            p_target = self.target_p1_w if robot_id == 1 else self.target_p2_w
            retract_p_w = p_target + np.array([0.0, 0.0, t_smooth * 0.12])
            target_p_local = R_BASE_90.T @ (retract_p_w - t_base)

            q_sol, _ = kinematics.inverse_kinematics(target_p_local, grasp_quat, q_current)
            grip_val = gripper_open

            is_finished = (self.step1 >= 30 and self.step2 >= 30)
            return q_sol, grip_val, is_finished

        return np.array(q_current), gripper_open, True


class ConveyorDualController(MultiRobotController):
    """Dual FR3 Controller extending the shared MultiRobotController engine."""

    def __init__(self):
        super().__init__(node_name='conveyor_dual_controller')
        self.active_robot_ids = [1, 2]
        self.conveyor_tracking = True
        self.conveyor_speed = 0.15

        # Active Trajectory Strategies
        self.circle_strategy: Optional[DualArmCircleTrajectory] = None
        self.place_strategy: Optional[DualArmPlaceTrajectory] = None

        # Vision Tracking Overlay Cache
        self.vision_tracked_objects: Dict[str, Any] = {}
        self.vision_sub = self.create_subscription(
            String, '/gemini/vision_tracked_objects', self._vision_tracked_cb, 10)

        self.get_logger().info("ConveyorDualController online (SOLID Trajectory Strategy Engine).")

    def _vision_tracked_cb(self, msg: String):
        try:
            data = json.loads(msg.data)
            self.vision_tracked_objects = data.get("objects", {})
        except Exception:
            pass

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

            # ── 2. DUAL ARM DRAW CIRCLE ───────────────────────────────────────
            elif action in ['dual_arm_circle', 'dual_arm_draw_circle', 'dual_arm_motion']:
                radius = float(cmd.get('radius', 0.08))
                cycles = int(cmd.get('cycles', 1))
                plane = str(cmd.get('plane', 'XY')).upper()
                speed = cmd.get('speed', 'fast')
                steps_per_cycle = 75 if speed == 'fast' else (150 if speed == 'slow' else 100)

                self.circle_strategy = DualArmCircleTrajectory(
                    radius=radius, cycles=cycles, plane=plane, steps_per_cycle=steps_per_cycle
                )
                self.circle_strategy.initialize(self.q_current1, self.q_current2)

                self._action_start_time['global'] = time.monotonic()
                for rid in [1, 2]:
                    self._action_start_time[rid] = time.monotonic()
                    setattr(self, f'gemini_action{rid}', 'dual_arm_circle')
                    self._set_state(rid, 'DUAL_ARM_CIRCLE')

                self.get_logger().info(f"[DUAL-ARM CIRCLE] Initiated {plane} circle (R={radius}m, cycles={cycles})")
                return

            # ── 3. DUAL ARM PLACE ─────────────────────────────────────────────
            elif action == 'dual_arm_place' or (action == 'place' and (self.state1 == 'WAITING_FOR_PLACE_CMD' or self.state2 == 'WAITING_FOR_PLACE_CMD')):
                speed = cmd.get('speed', 'fast')
                steps = 30 if speed == 'fast' else (70 if speed == 'slow' else 45)
                tx = float(cmd.get('x', 0.0))
                ty = float(cmd.get('y', 0.25))

                self.place_strategy = DualArmPlaceTrajectory(target_x=tx, target_y=ty, total_steps=steps)
                self.place_strategy.initialize(self.q_current1, self.q_current2)

                self._action_start_time['global'] = time.monotonic()
                for rid in [1, 2]:
                    self._action_start_time[rid] = time.monotonic()
                    setattr(self, f'gemini_action{rid}', 'dual_arm_place')
                    self._set_state(rid, 'DUAL_ARM_PLACE')

                self.get_logger().info(f"[DUAL-ARM PLACE] Initiated placement to bar center ({tx}, {ty})")
                return

            # All standard actions handled by base class
            super()._action_cb(msg)
        except Exception as e:
            self._publish_result(False, f"Action parsing failed: {e}")

    def get_block_local_pose(self, robot_id):
        """Retrieve block position and optimal grasp quaternion with vision tracking overlay."""
        is_dual_arm = getattr(self, f'gemini_action{robot_id}', None) == 'dual_arm_pick'
        name = self.get_target_block_name(robot_id)
        if not name:
            return None, None

        frame = self.get_robot_base_frame(robot_id)
        t_base = T_BASE1 if robot_id == 1 else T_BASE2

        # 1. Vision Tracker Overlay
        if self.vision_tracked_objects and name in self.vision_tracked_objects:
            p_world = np.array(self.vision_tracked_objects[name]["world_xyz"])
            p_local = R_BASE_90.T @ (p_world - t_base)

            if is_dual_arm:
                offset_dist = getattr(self, f'grasp_offset{robot_id}', -0.25 if robot_id == 1 else 0.25)
                p_local[0] += offset_dist
                arm_yaw = np.arctan2(p_local[1], p_local[0])
                target_quat = kinematics.compute_symmetric_grasp_quat(np.pi / 2.0, arm_yaw)
            else:
                arm_yaw = np.arctan2(p_local[1], p_local[0])
                target_quat = kinematics.compute_symmetric_grasp_quat(0.0, arm_yaw)

            return p_local, target_quat

        # 2. Fallback to TF Buffer
        try:
            trans = self.tf_buffer.lookup_transform(frame, name, rclpy.time.Time())
            p = trans.transform.translation
            q = trans.transform.rotation

            block_yaw = np.arctan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))

            if is_dual_arm:
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
        """Process robot state with dynamic visual servoing and strategy execution."""
        state = getattr(self, f'state{robot_id}')

        # ── 1. Circular Trajectory Strategy Execution ─────────────────────────
        if state == 'DUAL_ARM_CIRCLE' and self.circle_strategy is not None:
            q_cur = getattr(self, f'q_current{robot_id}')
            q_sol, is_finished = self.circle_strategy.step(robot_id, q_cur)

            cmd = JointState()
            cmd.header.stamp = self.get_clock().now().to_msg()
            cmd.name = self.joint_names_fr3
            cmd.position = list(q_sol) + [self.gripper_close, self.gripper_close]
            (self.cmd_pub1 if robot_id == 1 else self.cmd_pub2).publish(cmd)

            if robot_id == 1:
                for i in range(7): self.q_current1[i] = q_sol[i]
            else:
                for i in range(7): self.q_current2[i] = q_sol[i]

            if is_finished:
                self.circle_strategy = None
                self._set_state(1, 'WAITING_FOR_PLACE_CMD')
                self._set_state(2, 'WAITING_FOR_PLACE_CMD')
                self._publish_result(True, "Dual-arm synchronized circular motion completed successfully.", "global")
                self.get_logger().info("[DUAL-ARM CIRCLE] Trajectory completed successfully.")
            return

        # ── 2. Placement Trajectory Strategy Execution ────────────────────────
        if state == 'DUAL_ARM_PLACE' and self.place_strategy is not None:
            q_cur = getattr(self, f'q_current{robot_id}')
            q_sol, grip_val, is_finished = self.place_strategy.step(
                robot_id, q_cur, self.gripper_open, self.gripper_close
            )

            cmd = JointState()
            cmd.header.stamp = self.get_clock().now().to_msg()
            cmd.name = self.joint_names_fr3
            cmd.position = list(q_sol) + [grip_val, grip_val]
            (self.cmd_pub1 if robot_id == 1 else self.cmd_pub2).publish(cmd)

            if robot_id == 1:
                for i in range(7): self.q_current1[i] = q_sol[i]
            else:
                for i in range(7): self.q_current2[i] = q_sol[i]

            if is_finished:
                self.place_strategy = None
                self._set_state(1, 'FINISHED')
                self._set_state(2, 'FINISHED')
                self._publish_result(True, "Coordinated dual-arm placement completed successfully.", 1)
                self._publish_result(True, "Coordinated dual-arm placement completed successfully.", 2)
                self._publish_result(True, "Coordinated dual-arm placement completed successfully.", "global")
                self.get_logger().info("[DUAL-ARM PLACE] Placement completed with zero bar stress.")
            return

        # ── 3. Dynamic Conveyor Visual Servoing ────────────────────────────────
        if self.conveyor_tracking and state in ['HOVER_PICK', 'DESCEND_PICK']:
            block_pos, _ = self.get_block_local_pose(robot_id)
            if block_pos is not None:
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
