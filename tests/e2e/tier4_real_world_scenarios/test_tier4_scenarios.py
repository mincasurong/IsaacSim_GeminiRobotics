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


def test_mode5_longbar_auto_promotion_and_dual_place():
    v = RuleBasedTaskVerifier()
    ws = MockWS()
    ok, sanitized, reason = v.verify_action("pick", {"robot": "FR3_1", "object_label": "LongBar"}, ws)
    assert ok
    assert sanitized["action"] == "dual_arm_pick"
    assert v.robot_holding["FR3_1"] == "LongBar"
    assert v.robot_holding["FR3_2"] == "LongBar"
