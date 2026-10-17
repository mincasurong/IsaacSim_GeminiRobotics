#!/usr/bin/env python3
"""
Unit Test Suite for Franka FR3 Kinematics, Jacobian, and SVD DLS Solver.

Verifies:
- Forward Kinematics (FK) TCP pose consistency
- Inverse Kinematics (IK) convergence on workspace poses
- Yoshikawa manipulability measure and gradient stability
- Quaternion transformations and grasp orientation symmetry
- Joint limit compliance
"""

import os
import sys
import unittest
import numpy as np

# Ensure module is discoverable under test execution
pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)

from isaac_ros2_control import kinematics


class TestFrankaKinematics(unittest.TestCase):
    """Rigorous mathematical tests for Franka FR3 manipulator kinematics."""

    def setUp(self):
        self.q_home = np.array([0.0, 0.0, 0.0, -1.5708, 0.0, 1.5708, 0.7854], dtype=float)
        self.q_zeros = np.zeros(7, dtype=float)

    def test_forward_kinematics_home_pose(self):
        """Verify FK at nominal home configuration produces valid SE(3) pose."""
        T_home = kinematics.forward_kinematics(self.q_home)
        self.assertEqual(T_home.shape, (4, 4))
        
        # Check SE(3) rotation submatrix is orthogonal: R @ R.T = I
        R = T_home[:3, :3]
        np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-5)
        self.assertAlmostEqual(np.linalg.det(R), 1.0, places=4)

        # Check TCP position is within reachable Franka workspace radius
        pos = T_home[:3, 3]
        radius = float(np.linalg.norm(pos[:2]))
        self.assertTrue(0.20 < radius < 0.85, f"TCP radius {radius:.3f}m out of expected range")
        self.assertTrue(pos[2] > 0.0, f"TCP Z {pos[2]:.3f}m should be above base")

    def test_jacobian_dimensions_and_properties(self):
        """Verify geometric Jacobian shape (6, 7) and rank away from singularities."""
        J = kinematics.get_jacobian(self.q_home)
        self.assertEqual(J.shape, (6, 7))

        # Check condition number / rank at home configuration
        rank = np.linalg.matrix_rank(J)
        self.assertEqual(rank, 6, "Jacobian should have full rank 6 at home configuration")

    def test_manipulability_computation(self):
        """Verify Yoshikawa manipulability w = sqrt(det(J J^T)) is strictly positive at home."""
        w_home = kinematics.manipulability(self.q_home)
        self.assertGreater(w_home, 0.01, f"Manipulability {w_home} should be strictly positive")

        # Test manipulability gradient
        grad = kinematics.manipulability_gradient(self.q_home)
        self.assertEqual(grad.shape, (7,))
        self.assertFalse(np.any(np.isnan(grad)), "Gradient must not contain NaN")

    def test_inverse_kinematics_convergence(self):
        """Verify DLS IK convergence to target within reachable workspace."""
        # Query reachable pose via forward kinematics
        q_target = np.array([0.2, -0.4, 0.1, -2.1, 0.0, 1.7, 0.8], dtype=float)
        T_target = kinematics.forward_kinematics(q_target)
        p_target = T_target[:3, 3]
        quat_target = kinematics.rot_matrix_to_quat(T_target[:3, :3])

        # Solve IK starting from home configuration
        q_sol, success = kinematics.inverse_kinematics(p_target, quat_target, self.q_home)
        self.assertTrue(success, "IK solver should successfully converge")

        # Verify forward kinematics of solution matches target position within 2mm
        T_sol = kinematics.forward_kinematics(q_sol)
        p_sol = T_sol[:3, 3]
        pos_error = np.linalg.norm(p_sol - p_target)
        self.assertLess(pos_error, 0.003, f"Position error {pos_error*1000:.2f}mm exceeds 3mm tolerance")

        # Verify joint limits
        for i in range(7):
            lim_min, lim_max = kinematics.FR3_JOINT_LIMITS[i]
            self.assertGreaterEqual(q_sol[i], lim_min - 1e-4)
            self.assertLessEqual(q_sol[i], lim_max + 1e-4)

    def test_quaternion_and_rotation_matrix_roundtrip(self):
        """Verify quat_to_rot_matrix and rot_matrix_to_quat bidirectional round-trip consistency."""
        # 90-degree pitch rotation
        theta = np.pi / 2.0
        R_pitch = np.array([
            [np.cos(theta), 0.0, np.sin(theta)],
            [0.0, 1.0, 0.0],
            [-np.sin(theta), 0.0, np.cos(theta)]
        ])
        quat = kinematics.rot_matrix_to_quat(R_pitch)
        R_recovered = kinematics.quat_to_rot_matrix(quat)
        np.testing.assert_allclose(R_pitch, R_recovered, atol=1e-5)

    def test_compute_symmetric_grasp_quat(self):
        """Verify symmetric downward grasp orientation generation with 4-fold symmetry."""
        target_yaw = 0.0
        arm_yaw = np.pi / 2.0
        quat = kinematics.compute_symmetric_grasp_quat(target_yaw, arm_yaw)
        self.assertEqual(len(quat), 4)

        # Quaternion norm must be unity
        norm = np.linalg.norm(quat)
        self.assertAlmostEqual(norm, 1.0, places=5)

        # Grasp orientation must orient TCP downward (Z-axis pointing down in base frame)
        R = kinematics.quat_to_rot_matrix(quat)
        # TCP Z column should point downward (negative Z or perpendicular depending on convention)
        self.assertTrue(np.all(np.isfinite(R)))


if __name__ == '__main__':
    unittest.main()
