import sys
from pathlib import Path
import numpy as np
import pytest

PKG_ROOT = Path(__file__).resolve().parents[3] / "wsl_ws" / "src" / "isaac_ros2_control"
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(PKG_ROOT))

from isaac_ros2_control import kinematics
from isaac_ros2_control.conveyor_dual_controller import DualArmPickTrajectory


def test_fk_ik_roundtrip_home():
    q_home = np.array([0.0, 0.0, 0.0, -1.5708, 0.0, 1.5708, 0.7854], dtype=float)
    T = kinematics.forward_kinematics(q_home)
    pos = T[:3, 3]
    quat = kinematics.rot_matrix_to_quat(T[:3, :3])
    q_sol, ok = kinematics.inverse_kinematics(pos, quat, q_home)
    assert ok
    T_sol = kinematics.forward_kinematics(q_sol)
    assert np.allclose(T[:3, 3], T_sol[:3, 3], atol=2e-3)


def test_bimanual_pick_trajectory():
    q_home = [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]
    quat = kinematics.compute_symmetric_grasp_quat(np.pi / 2.0, np.pi / 2.0)
    pick = DualArmPickTrajectory(
        bar_pos_w=np.array([0.0, 0.0, 0.345]),
        off1=-0.20,
        off2=0.20,
        hover_height=0.10,
        steps=5,
    )
    pick.initialize(q_home, q_home, quat, quat)
    q1, q2 = np.array(q_home), np.array(q_home)
    fin1 = fin2 = False
    for _ in range(50):
        q1, _, fin1 = pick.step(1, q1, 0.04, 0.015)
        q2, _, fin2 = pick.step(2, q2, 0.04, 0.015)
        if fin1 and fin2:
            break
    assert fin1 and fin2
