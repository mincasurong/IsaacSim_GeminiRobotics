from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np


@dataclass
class FaultDiagnostic:
    tier: int
    classification: str
    failed_node_id: str
    displaced_blocks: List[str]
    max_displacement_mm: float
    height_drop_mm: float
    lower_layers_intact: bool
    perturbed_poses: Dict[str, List[float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": int(self.tier),
            "classification": self.classification,
            "failed_node_id": self.failed_node_id,
            "displaced_blocks": list(self.displaced_blocks),
            "max_displacement_mm": round(float(self.max_displacement_mm), 3),
            "height_drop_mm": round(float(self.height_drop_mm), 3),
            "lower_layers_intact": bool(self.lower_layers_intact),
            "perturbed_poses": self.perturbed_poses,
        }

    def to_spatial_architect_constraint_prompt(self) -> str:
        return (
            f"[TIER-2 TOPOLOGICAL COLLAPSE AT {self.failed_node_id}] "
            f"Perturbed block poses fixed as obstacle/base constraints: {json.dumps(self.perturbed_poses)}"
        )


class FaultClassifier:
    def __init__(
        self,
        tier1_min_slip_mm: float = 3.0,
        tier1_max_slip_mm: float = 50.0,
        block_thickness_mm: float = 45.0,
    ):
        self.tier1_min_slip_mm = float(tier1_min_slip_mm)
        self.tier1_max_slip_mm = float(tier1_max_slip_mm)
        self.block_thickness_mm = float(block_thickness_mm)

    def evaluate_poses(
        self,
        expected_poses: Dict[str, Sequence[float]],
        observed_poses: Dict[str, Sequence[float]],
        active_node_id: str = "layer_4_place",
        active_block_id: Optional[str] = None,
    ) -> FaultDiagnostic:
        displaced_blocks: List[str] = []
        max_disp_mm = 0.0
        max_height_drop_mm = 0.0
        lower_layers_intact = True
        perturbed: Dict[str, List[float]] = {}

        block_keys = list(expected_poses.keys())
        target_block = active_block_id or (block_keys[-1] if block_keys else "Block1")

        for b_id, exp in expected_poses.items():
            obs = observed_poses.get(b_id, exp)
            exp_arr = np.array(exp[:3], dtype=float)
            obs_arr = np.array(obs[:3], dtype=float)
            perturbed[b_id] = [round(float(x), 4) for x in obs_arr]

            disp_mm = float(np.linalg.norm(obs_arr - exp_arr)) * 1000.0
            drop_mm = max(0.0, float(exp_arr[2] - obs_arr[2]) * 1000.0)

            if disp_mm > self.tier1_min_slip_mm:
                displaced_blocks.append(b_id)
                if b_id != target_block:
                    lower_layers_intact = False
            if disp_mm > max_disp_mm:
                max_disp_mm = disp_mm
            if drop_mm > max_height_drop_mm:
                max_height_drop_mm = drop_mm

        if not displaced_blocks:
            return FaultDiagnostic(
                tier=0,
                classification="NOMINAL",
                failed_node_id=active_node_id,
                displaced_blocks=[],
                max_displacement_mm=max_disp_mm,
                height_drop_mm=max_height_drop_mm,
                lower_layers_intact=True,
                perturbed_poses=perturbed,
            )

        is_single_block = len(displaced_blocks) == 1
        within_tier1_bounds = self.tier1_min_slip_mm < max_disp_mm < self.tier1_max_slip_mm
        no_collapse_drop = max_height_drop_mm <= self.block_thickness_mm

        if is_single_block and within_tier1_bounds and lower_layers_intact and no_collapse_drop:
            return FaultDiagnostic(
                tier=1,
                classification="TIER1_LOCAL_POSE_SLIP",
                failed_node_id=active_node_id,
                displaced_blocks=displaced_blocks,
                max_displacement_mm=max_disp_mm,
                height_drop_mm=max_height_drop_mm,
                lower_layers_intact=True,
                perturbed_poses=perturbed,
            )

        return FaultDiagnostic(
            tier=2,
            classification="TIER2_TOPOLOGICAL_COLLAPSE",
            failed_node_id=active_node_id,
            displaced_blocks=displaced_blocks,
            max_displacement_mm=max_disp_mm,
            height_drop_mm=max_height_drop_mm,
            lower_layers_intact=False,
            perturbed_poses=perturbed,
        )
