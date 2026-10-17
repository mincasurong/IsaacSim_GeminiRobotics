import sys
from pathlib import Path
import numpy as np
import pytest

PKG_ROOT = Path(__file__).resolve().parents[3] / "wsl_ws" / "src" / "isaac_ros2_control"
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(PKG_ROOT))

from isaac_ros2_control import kinematics
from isaac_ros2_control.conveyor_dual_controller import DualArmCircleTrajectory


@pytest.mark.parametrize("robot_id", [1, 2])
@pytest.mark.parametrize("plane", ["XY", "XZ"])
def test_dual_arm_circle_planes_and_arms(robot_id, plane):
    q_home = [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]
    quat = kinematics.compute_symmetric_grasp_quat(np.pi / 2.0, np.pi / 2.0)
    traj = DualArmCircleTrajectory(radius=0.05, cycles=1, plane=plane, steps_per_cycle=12)
    traj.initialize(q_home, q_home)
    q_cmd, fin = traj.step(robot_id, q_home)
    assert len(q_cmd) == 7
    assert np.all(np.isfinite(q_cmd))
    assert not fin
