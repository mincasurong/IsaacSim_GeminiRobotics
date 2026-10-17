from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np


@dataclass
class ModelRouteDecision:
    role: str
    selected_model: str
    routing_score: float
    escalated: bool
    nearby_blocks_count: int
    active_rejection_certificates: int
    estimated_latency_ms: float
    estimated_token_cost: int
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "selected_model": self.selected_model,
            "routing_score": round(self.routing_score, 3),
            "escalated": bool(self.escalated),
            "nearby_blocks_count": int(self.nearby_blocks_count),
            "active_rejection_certificates": int(self.active_rejection_certificates),
            "estimated_latency_ms": round(self.estimated_latency_ms, 2),
            "estimated_token_cost": int(self.estimated_token_cost),
            "reason": self.reason,
        }


class HeterogeneousModelRouter:
    def __init__(
        self,
        heavy_model: Optional[str] = None,
        fast_model: Optional[str] = None,
        congestion_radius_m: float = 0.100,
        congestion_threshold: int = 3,
    ):
        self.heavy_model = heavy_model or os.environ.get("ROBOTICS_MODEL", "gemini-robotics-er-2-preview")
        self.fast_model = fast_model or os.environ.get("PLANNER_MODEL", "gemini-3.5-flash-lite")
        self.congestion_radius_m = float(congestion_radius_m)
        self.congestion_threshold = int(congestion_threshold)

        self.decisions: List[ModelRouteDecision] = []

    def count_congested_blocks(
        self,
        block_positions: Sequence[Sequence[float]],
        target_xy: Sequence[float] = (0.0, 0.0),
    ) -> int:
        if not block_positions:
            return 0
        target = np.array(target_xy[:2], dtype=float)
        count = 0
        for pos in block_positions:
            p = np.array(pos[:2], dtype=float)
            if float(np.linalg.norm(p - target)) <= self.congestion_radius_m:
                count += 1
        return count

    def route_turn(
        self,
        role: str,
        block_positions: Optional[Sequence[Sequence[float]]] = None,
        target_xy: Sequence[float] = (0.0, 0.0),
        active_gate_rejections: int = 0,
        tier2_recovery: bool = False,
    ) -> ModelRouteDecision:
        role_norm = str(role or "agility_optimizer").strip().lower()
        nearby_count = self.count_congested_blocks(block_positions or [], target_xy=target_xy)

        role_weight = 1.0 if (role_norm in ("spatial_architect", "tier2_recovery", "orchestrator_complex") or tier2_recovery) else 0.0
        score = (1.0 * int(active_gate_rejections)) + (0.35 * nearby_count) + role_weight

        if int(active_gate_rejections) > 0:
            escalated = True
            selected = self.heavy_model
            reason = f"Escalated to {self.heavy_model}: active GateRejectionCertificate count={active_gate_rejections}"
        elif tier2_recovery or role_norm in ("spatial_architect", "tier2_recovery"):
            escalated = True
            selected = self.heavy_model
            reason = f"Assigned {self.heavy_model} for high-reasoning role '{role_norm}'"
        elif nearby_count >= self.congestion_threshold or score >= 1.0:
            escalated = True
            selected = self.heavy_model
            reason = f"Escalated to {self.heavy_model}: congestion={nearby_count} blocks within 100mm (score={score:.2f})"
        else:
            escalated = False
            selected = self.fast_model
            reason = f"Routed to fast model {self.fast_model} for routine '{role_norm}' (score={score:.2f})"

        est_latency_ms = 820.0 if escalated else 240.0
        est_tokens = 1450 if escalated else 420

        decision = ModelRouteDecision(
            role=role_norm,
            selected_model=selected,
            routing_score=score,
            escalated=escalated,
            nearby_blocks_count=nearby_count,
            active_rejection_certificates=int(active_gate_rejections),
            estimated_latency_ms=est_latency_ms,
            estimated_token_cost=est_tokens,
            reason=reason,
        )
        self.decisions.append(decision)
        return decision

    def get_pareto_metrics(self) -> Dict[str, Any]:
        if not self.decisions:
            return {
                "planning_wall_clock_ms": 0.0,
                "model_escalation_ratio": 0.0,
                "total_token_cost": 0,
                "turns_routed": 0,
            }
        total_ms = sum(d.estimated_latency_ms for d in self.decisions)
        escalated_count = sum(1 for d in self.decisions if d.escalated)
        total_tokens = sum(d.estimated_token_cost for d in self.decisions)
        return {
            "planning_wall_clock_ms": round(total_ms, 2),
            "model_escalation_ratio": round(escalated_count / len(self.decisions), 4),
            "total_token_cost": int(total_tokens),
            "turns_routed": len(self.decisions),
            "turn_breakdown": [d.to_dict() for d in self.decisions],
        }
