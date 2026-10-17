import sys
from pathlib import Path
import numpy as np
import pytest

PKG_ROOT = Path(__file__).resolve().parents[3] / "wsl_ws" / "src" / "isaac_ros2_control"
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(PKG_ROOT))

from isaac_ros2_control import kinematics
from isaac_ros2_control.conveyor_dual_controller import (
    DualArmPickTrajectory,
    DualArmPlaceTrajectory,
    DualArmCircleTrajectory,
    quintic_smoothstep,
    world_to_local_base,
    local_base_to_world,
)
from isaac_ros2_control.rule_based_verifier import (
    RuleBasedTaskVerifier,
    RuleBasedTaskGenerator,
    resolve_block_name,
    normalize_robot_id,
)


class MockWS:
    def __init__(self):
        self.blocks_on_tower = []
        self.tower_height = 0
        self.holding = {"FR3_1": None, "FR3_2": None, "FR3_3": None}
        self.block_status = {
            "Block1": {"pos": np.array([0.0, -1.0, 0.35]), "held_by": None},
            "Block4": {"pos": np.array([0.85, 0.5, 0.35]), "held_by": None},
            "Block7": {"pos": np.array([-0.85, 0.5, 0.35]), "held_by": None},
        }

    def get_summary(self):
        return {
            "tower": {"layers": self.tower_height, "blocks": self.blocks_on_tower},
            "robots": self.holding,
        }


def test_quintic_smoothstep_clamping():
    assert quintic_smoothstep(-1.0) == pytest.approx(0.0)
    assert quintic_smoothstep(0.0) == pytest.approx(0.0)
    assert quintic_smoothstep(0.5) == pytest.approx(0.5)
    assert quintic_smoothstep(1.0) == pytest.approx(1.0)
    assert quintic_smoothstep(2.5) == pytest.approx(1.0)


def test_verifier_rejects_unreachable_and_out_of_bounds():
    v = RuleBasedTaskVerifier()
    ws = MockWS()
    v.verify_action("pick", {"robot": "FR3_2", "object_label": "Block4"}, ws)
    ok, _, msg = v.verify_action("place", {"robot": "FR3_2", "x": 5.0, "y": 5.0}, ws)
    assert not ok
    assert "do not lie on any valid table" in msg
