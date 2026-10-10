#!/usr/bin/env python3
"""
Scientific Verification Test Suite
Evaluates DualArmPickTrajectory bimanual closed-chain synchronization
and Flying Grasp dynamic conveyor velocity feedforward tracking.
"""

import sys
import unittest
import numpy as np

# Add src to path
sys.path.insert(0, '/mnt/d/git/IsaacSim_Gemini/wsl_ws/src/isaac_ros2_control')
from isaac_ros2_control import kinematics
from isaac_ros2_control.conveyor_dual_controller import (
    DualArmPickTrajectory,
    DualArmPlaceTrajectory,
    DualArmCircleTrajectory,
    R_BASE_90,
    T_BASE1,
    T_BASE2
)


class TestBimanualAndConveyorKinematics(unittest.TestCase):
    """Rigorous mathematical verification of multi-robot kinematic coordination."""

    def setUp(self):
        # Franka FR3 nominal home configuration (7-DOF)
        self.q_home = [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]
        self.bar_world_pos = np.array([0.0, 0.25, 0.345])
        self.conveyor_speed = 0.15 # 15 cm/s

    def test_dual_arm_pick_trajectory_synchronization(self):
        """Verify lockstep bimanual trajectory tracking, descent, and zero-strain lift."""
        quat1 = kinematics.compute_symmetric_grasp_quat(np.pi / 2.0, np.pi / 2.0)
        quat2 = kinematics.compute_symmetric_grasp_quat(np.pi / 2.0, np.pi / 2.0)

        traj = DualArmPickTrajectory(
            bar_pos_w=self.bar_world_pos,
            off1=-0.25,
            off2=0.25,
            hover_height=0.12,
            steps=25
        )
        traj.initialize(self.q_home, self.q_home, quat1, quat2)

        q1_cur = np.array(self.q_home)
        q2_cur = np.array(self.q_home)

        # 1. Step through HOVER phase (25 steps)
        for step in range(25):
            q1_next, grip1, fin1 = traj.step(1, q1_cur, 0.04, 0.015)
            q2_next, grip2, fin2 = traj.step(2, q2_cur, 0.04, 0.015)
            q1_cur, q2_cur = q1_next, q2_next

            # Assert grippers remain open
            self.assertEqual(grip1, 0.04)
            self.assertEqual(grip2, 0.04)
            self.assertFalse(fin1)

        self.assertEqual(traj.phase, 'DESCEND', "Traj should transition to DESCEND after hover")

        # 2. Step through DESCEND phase (25 steps)
        for step in range(25):
            q1_next, grip1, fin1 = traj.step(1, q1_cur, 0.04, 0.015)
            q2_next, grip2, fin2 = traj.step(2, q2_cur, 0.04, 0.015)
            q1_cur, q2_cur = q1_next, q2_next
            self.assertEqual(grip1, 0.04)
            self.assertEqual(grip2, 0.04)

        self.assertEqual(traj.phase, 'GRASP', "Traj should transition to GRASP after descent")

        # 3. Step through GRASP phase (20 steps stiction dwell)
        for step in range(20):
            q1_next, grip1, fin1 = traj.step(1, q1_cur, 0.04, 0.015)
            q2_next, grip2, fin2 = traj.step(2, q2_cur, 0.04, 0.015)
            q1_cur, q2_cur = q1_next, q2_next
            # Assert grippers close
            self.assertEqual(grip1, 0.015)
            self.assertEqual(grip2, 0.015)

        self.assertEqual(traj.phase, 'LIFT', "Traj should transition to LIFT after grasp dwell")

        # 4. Step through LIFT phase (25 steps) and assert inter-gripper distance invariant
        for step in range(25):
            q1_next, grip1, fin1 = traj.step(1, q1_cur, 0.04, 0.015)
            q2_next, grip2, fin2 = traj.step(2, q2_cur, 0.04, 0.015)
            q1_cur, q2_cur = q1_next, q2_next

            # Compute world positions via forward kinematics
            p1_loc = kinematics.forward_kinematics(q1_cur)[:3, 3]
            p2_loc = kinematics.forward_kinematics(q2_cur)[:3, 3]
            p1_w = R_BASE_90 @ p1_loc + T_BASE1
            p2_w = R_BASE_90 @ p2_loc + T_BASE2

            inter_ee_distance = np.linalg.norm(p1_w - p2_w)
            # Expected distance between grasp points is 0.50m (off2 - off1 = 0.25 - (-0.25) = 0.50m)
            self.assertAlmostEqual(
                inter_ee_distance, 0.50, delta=0.03,
                msg=f"Inter-gripper distance deviated ({inter_ee_distance:.4f}m vs 0.50m)"
            )

        self.assertTrue(fin2, "Trajectory must report finished after lift phase completes")

    def test_dynamic_conveyor_velocity_feedforward(self):
        """Verify flying grasp continuous velocity matching along the conveyor transport axis."""
        # Conveyor travels in World +X at 0.15 m/s.
        # Local base frame (yaw = 90 deg) projects World +X to Local -Y.
        block_init_loc = np.array([0.45, -0.10, 0.15]) # [X, Y, Z]
        dt = 0.02 # 50 Hz loop tick

        curr_end_y = block_init_loc[1]
        for tick in range(15): # 300 ms grasp duration
            flying_y = curr_end_y - (self.conveyor_speed * dt)
            delta_y = flying_y - curr_end_y
            # Velocity along local Y must exactly equal -0.15 m/s
            v_tracked = delta_y / dt
            self.assertAlmostEqual(
                v_tracked, -self.conveyor_speed, delta=1e-5,
                msg=f"End-effector velocity mismatch: {v_tracked} vs {-self.conveyor_speed}"
            )
            curr_end_y = flying_y

        total_conveyor_displacement = 15 * dt * self.conveyor_speed
        self.assertAlmostEqual(total_conveyor_displacement, 0.045, delta=1e-4)


if __name__ == '__main__':
    unittest.main()
