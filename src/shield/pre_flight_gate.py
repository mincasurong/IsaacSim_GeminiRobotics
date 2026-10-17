from __future__ import annotations

import copy
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONTROL_DIR = _REPO_ROOT / "wsl_ws" / "src" / "isaac_ros2_control" / "isaac_ros2_control"
if str(_CONTROL_DIR) not in sys.path and _CONTROL_DIR.exists():
    sys.path.insert(0, str(_CONTROL_DIR))

try:
    import kinematics
except ImportError:
    from isaac_ros2_control import kinematics


ROBOT_BASES: Dict[str, Tuple[np.ndarray, float]] = {
    "FR3_1": (np.array([0.0, -0.45, 0.20], dtype=float), math.radians(168.0)),
    "FR3_2": (np.array([0.3897, 0.225, 0.20], dtype=float), math.radians(-64.0)),
    "FR3_3": (np.array([-0.3897, 0.225, 0.20], dtype=float), math.radians(42.0)),
    "fr3_arm_1": (np.array([0.0, -0.45, 0.20], dtype=float), math.radians(168.0)),
    "fr3_arm_2": (np.array([0.3897, 0.225, 0.20], dtype=float), math.radians(-64.0)),
    "fr3_arm_3": (np.array([-0.3897, 0.225, 0.20], dtype=float), math.radians(42.0)),
}


@dataclass
class GateRejectionCertificate:
    status: str
    node_id: str
    arm_id: str
    violation_type: str
    measured_value: float
    limit_value: float
    unit: str
    correction_hint: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "node_id": self.node_id,
            "arm_id": self.arm_id,
            "violation_type": self.violation_type,
            "measured_value": round(float(self.measured_value), 3),
            "limit_value": round(float(self.limit_value), 3),
            "unit": self.unit,
            "correction_hint": self.correction_hint,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_context_prompt(self) -> str:
        return (
            f"[PRE-FLIGHT GATE REJECTION CERTIFICATE] {json.dumps(self.to_dict())} "
            f"-> Repair ONLY node '{self.node_id}' ({self.correction_hint}); keep upstream nodes unchanged."
        )


class PreFlightGate:
    def __init__(
        self,
        mode: str = "strict",
        block_width_m: float = 0.045,
        min_overhang_margin_mm: float = 5.0,
        min_reach_m: float = 0.15,
        max_reach_m: float = 0.85,
        ee_half_extents_m: Tuple[float, float, float] = (0.045, 0.045, 0.060),
        central_zone_half_width_m: float = 0.18,
    ):
        if mode not in ("off", "strict"):
            raise ValueError(f"Unsupported shield mode '{mode}'. Expected 'off' or 'strict'.")
        self.mode = mode
        self.block_width_m = float(block_width_m)
        self.half_width_m = float(block_width_m) / 2.0
        self.min_overhang_margin_mm = float(min_overhang_margin_mm)
        self.min_overhang_margin_m = float(min_overhang_margin_mm) / 1000.0
        self.min_reach_m = float(min_reach_m)
        self.max_reach_m = float(max_reach_m)
        self.ee_half_extents_m = np.array(ee_half_extents_m, dtype=float)
        self.central_zone_half_width_m = float(central_zone_half_width_m)

        self.total_proposals_evaluated: int = 0
        self.gate_interception_count: int = 0
        self.write_back_iterations: int = 0

    @property
    def invalid_proposal_rejection_rate(self) -> float:
        if self.total_proposals_evaluated == 0:
            return 0.0
        return round(float(self.gate_interception_count) / float(self.total_proposals_evaluated), 4)

    def get_telemetry(self) -> Dict[str, Any]:
        return {
            "shield_mode": self.mode,
            "total_proposals_evaluated": self.total_proposals_evaluated,
            "gate_interception_count": self.gate_interception_count,
            "write_back_iterations": self.write_back_iterations,
            "invalid_proposal_rejection_rate": self.invalid_proposal_rejection_rate,
        }

    @staticmethod
    def _normalize_arm_id(arm_id: str) -> str:
        norm = str(arm_id or "FR3_1").strip()
        if norm.lower().startswith("fr3_arm_"):
            idx = norm.split("_")[-1]
            return f"FR3_{idx}"
        if norm.upper().startswith("FR3_"):
            return norm.upper()
        return "FR3_1"

    @staticmethod
    def _format_arm_id(arm_id: str) -> str:
        norm = PreFlightGate._normalize_arm_id(arm_id)
        idx = norm.split("_")[-1]
        return f"fr3_arm_{idx}"

    def check_static_stability(
        self,
        tower_layers: List[Sequence[float]],
        proposed_pose: Sequence[float],
        node_id: str = "layer_k_block",
        arm_id: str = "fr3_arm_1",
    ) -> Tuple[bool, Optional[GateRejectionCertificate]]:
        if self.mode == "off" or not tower_layers:
            return True, None

        stack = [np.array(layer[:2], dtype=float) for layer in tower_layers]
        p_new = np.array(proposed_pose[:2], dtype=float)
        full_stack = stack + [p_new]
        k = len(stack)

        worst_margin_mm = float("inf")
        worst_shift_mm = np.zeros(2, dtype=float)
        worst_support_idx = k

        for j in range(k):
            support_center = full_stack[j]
            upper_blocks = np.array(full_stack[j + 1 :], dtype=float)
            com_xy = np.mean(upper_blocks, axis=0)
            delta_xy = com_xy - support_center
            max_offset_m = float(np.max(np.abs(delta_xy)))
            margin_m = self.half_width_m - max_offset_m
            margin_mm = margin_m * 1000.0
            if margin_mm < worst_margin_mm:
                worst_margin_mm = margin_mm
                worst_support_idx = j + 1
                allowed_offset_m = max(0.0, self.half_width_m - self.min_overhang_margin_m)
                n_upper = len(upper_blocks)
                excess_x = 0.0
                excess_y = 0.0
                if abs(delta_xy[0]) > allowed_offset_m:
                    excess_x = math.copysign(abs(delta_xy[0]) - allowed_offset_m, delta_xy[0]) * n_upper
                if abs(delta_xy[1]) > allowed_offset_m:
                    excess_y = math.copysign(abs(delta_xy[1]) - allowed_offset_m, delta_xy[1]) * n_upper
                worst_shift_mm = np.array([-excess_x * 1000.0, -excess_y * 1000.0], dtype=float)

        if worst_margin_mm < self.min_overhang_margin_mm:
            overhang_beyond_safe_mm = (self.half_width_m * 1000.0) - worst_margin_mm
            cert = GateRejectionCertificate(
                status="REJECT",
                node_id=node_id,
                arm_id=self._format_arm_id(arm_id),
                violation_type="COM_OVERHANG",
                measured_value=round(float(overhang_beyond_safe_mm), 2),
                limit_value=round(float(self.min_overhang_margin_mm), 2),
                unit="mm",
                correction_hint=(
                    f"Shift placement [{worst_shift_mm[0]:+.1f}mm, {worst_shift_mm[1]:+.1f}mm] "
                    f"toward layer_{worst_support_idx} centroid"
                ),
            )
            return False, cert

        return True, None

    def check_reachability_and_bounds(
        self,
        arm_id: str,
        target_pose: Sequence[float],
        node_id: str = "node_ik",
    ) -> Tuple[bool, Optional[GateRejectionCertificate]]:
        if self.mode == "off":
            return True, None

        norm_arm = self._normalize_arm_id(arm_id)
        base_pos, base_yaw = ROBOT_BASES.get(norm_arm, ROBOT_BASES["FR3_1"])

        tx = float(target_pose[0])
        ty = float(target_pose[1])
        tz = float(target_pose[2]) if len(target_pose) >= 3 else 0.335
        tyaw = float(target_pose[3]) if len(target_pose) >= 4 else 0.0

        p_w = np.array([tx, ty, tz], dtype=float)
        dp_w = p_w - base_pos
        radial_dist_m = float(np.linalg.norm(dp_w[:2]))
        dist_3d_m = float(np.linalg.norm(dp_w))

        if radial_dist_m > self.max_reach_m or dist_3d_m > (self.max_reach_m + 0.05) or radial_dist_m < self.min_reach_m or tz < 0.18 or tz > 1.15:
            direction = base_pos[:2] - p_w[:2]
            norm_dir = float(np.linalg.norm(direction))
            unit_dir = (direction / norm_dir) if norm_dir > 1e-6 else np.array([1.0, 0.0])
            excess_m = max(0.0, radial_dist_m - (self.max_reach_m - 0.05))
            shift_mm = unit_dir * (excess_m * 1000.0)
            cert = GateRejectionCertificate(
                status="REJECT",
                node_id=node_id,
                arm_id=self._format_arm_id(arm_id),
                violation_type="IK_OUT_OF_BOUNDS",
                measured_value=round(radial_dist_m * 1000.0, 2),
                limit_value=round(self.max_reach_m * 1000.0, 2),
                unit="mm",
                correction_hint=(
                    f"Shift placement [{shift_mm[0]:+.1f}mm, {shift_mm[1]:+.1f}mm] "
                    f"into {norm_arm} reachable workspace ([{self.min_reach_m*1000:.0f}mm, {self.max_reach_m*1000:.0f}mm])"
                ),
            )
            return False, cert

        c_yaw = math.cos(-base_yaw)
        s_yaw = math.sin(-base_yaw)
        R_inv = np.array([[c_yaw, -s_yaw, 0.0], [s_yaw, c_yaw, 0.0], [0.0, 0.0, 1.0]], dtype=float)
        p_local = R_inv @ dp_w
        arm_yaw_local = math.atan2(float(p_local[1]), float(p_local[0]))
        target_quat = kinematics.compute_symmetric_grasp_quat(tyaw - base_yaw, arm_yaw_local)

        q_init = np.array(kinematics.FR3_HOME_CONFIG, dtype=float)
        q_init[0] = np.clip(arm_yaw_local, -2.85, 2.85)
        q_sol, ik_ok = kinematics.inverse_kinematics(p_local, target_quat, q_init, max_iter=150, tol=1e-3)
        fk_pos = kinematics.forward_kinematics(q_sol)[:3, 3]
        ik_err_mm = float(np.linalg.norm(fk_pos - p_local)) * 1000.0

        limits_low = getattr(kinematics, "FR3_JOINTS_LOWER", [-2.7437, -1.7837, -2.9007, -3.0421, -2.8065, 0.5445, -3.0159])
        limits_high = getattr(kinematics, "FR3_JOINTS_UPPER", [2.7437, 1.7837, 2.9007, -0.1518, 2.8065, 4.5169, 3.0159])
        limits_ok = True
        for q_val, low, high in zip(q_sol, limits_low, limits_high):
            if float(q_val) < float(low) - 1e-3 or float(q_val) > float(high) + 1e-3:
                limits_ok = False
                break

        if (not ik_ok and ik_err_mm > 15.0) or not limits_ok:
            cert = GateRejectionCertificate(
                status="REJECT",
                node_id=node_id,
                arm_id=self._format_arm_id(arm_id),
                violation_type="IK_OUT_OF_BOUNDS",
                measured_value=round(ik_err_mm, 2),
                limit_value=15.0,
                unit="mm",
                correction_hint=(
                    f"Target [{tx:.3f}, {ty:.3f}, {tz:.3f}] exceeds {norm_arm} IK/joint limits "
                    f"(residual {ik_err_mm:.1f}mm); reassign to nearest arm or move target toward [0.0, 0.0]"
                ),
            )
            return False, cert

        return True, None

    def check_swept_volume_aabb(
        self,
        concurrent_nodes: List[Dict[str, Any]],
    ) -> Tuple[bool, Optional[GateRejectionCertificate]]:
        if self.mode == "off" or len(concurrent_nodes) < 2:
            return True, None

        central_entries: List[Tuple[Dict[str, Any], np.ndarray, np.ndarray, np.ndarray]] = []
        for node in concurrent_nodes:
            tx = float(node.get("x", 0.0))
            ty = float(node.get("y", 0.0))
            tz = float(node.get("z", 0.335))
            pos = np.array([tx, ty, tz], dtype=float)
            if abs(tx) <= self.central_zone_half_width_m and abs(ty) <= self.central_zone_half_width_m:
                aabb_min = pos - self.ee_half_extents_m
                aabb_max = pos + self.ee_half_extents_m
                central_entries.append((node, pos, aabb_min, aabb_max))

        for i in range(len(central_entries)):
            node_a, _, min_a, max_a = central_entries[i]
            arm_a = self._normalize_arm_id(node_a.get("robot", node_a.get("arm_id", "FR3_1")))
            for j in range(i + 1, len(central_entries)):
                node_b, _, min_b, max_b = central_entries[j]
                arm_b = self._normalize_arm_id(node_b.get("robot", node_b.get("arm_id", "FR3_2")))
                if arm_a == arm_b:
                    continue
                overlap = np.minimum(max_a, max_b) - np.maximum(min_a, min_b)
                if np.all(overlap > 0.0):
                    penetration_mm = float(np.min(overlap)) * 1000.0
                    node_id = str(node_b.get("id", node_b.get("node_id", "concurrent_place")))
                    cert = GateRejectionCertificate(
                        status="REJECT",
                        node_id=node_id,
                        arm_id=self._format_arm_id(arm_b),
                        violation_type="SWEPT_VOLUME_COLLISION",
                        measured_value=round(penetration_mm, 2),
                        limit_value=0.0,
                        unit="mm",
                        correction_hint=(
                            f"Serialize {arm_b} node '{node_id}' after {arm_a} node "
                            f"'{node_a.get('id', 'place')}' on M_center or offset staging pose outside [-180mm, +180mm]"
                        ),
                    )
                    return False, cert

        return True, None

    def validate_proposal(
        self,
        node: Dict[str, Any],
        tower_layers: Optional[List[Sequence[float]]] = None,
        concurrent_nodes: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[bool, Optional[GateRejectionCertificate]]:
        self.total_proposals_evaluated += 1
        if self.mode == "off":
            return True, None

        node_id = str(node.get("id", node.get("node_id", "node_0")))
        arm_id = str(node.get("robot", node.get("arm_id", "FR3_1")))
        action = str(node.get("action", "place")).lower()

        tx = float(node.get("x", 0.0))
        ty = float(node.get("y", 0.0))
        tz = float(node.get("z", 0.335))
        tyaw = float(node.get("yaw", 0.0))

        if "x" in node or "y" in node or action in ("place", "pick"):
            ok_ik, cert_ik = self.check_reachability_and_bounds(arm_id, [tx, ty, tz, tyaw], node_id=node_id)
            if not ok_ik:
                self.gate_interception_count += 1
                return False, cert_ik

        if action in ("place", "replace_verified") and tower_layers:
            ok_com, cert_com = self.check_static_stability(tower_layers, [tx, ty, tz], node_id=node_id, arm_id=arm_id)
            if not ok_com:
                self.gate_interception_count += 1
                return False, cert_com

        if concurrent_nodes:
            ok_aabb, cert_aabb = self.check_swept_volume_aabb([node] + list(concurrent_nodes))
            if not ok_aabb:
                self.gate_interception_count += 1
                return False, cert_aabb

        return True, None

    def validate(
        self,
        dag: Dict[str, Any],
        initial_tower_layers: Optional[List[Sequence[float]]] = None,
    ) -> Tuple[bool, List[GateRejectionCertificate]]:
        if self.mode == "off":
            return True, []

        nodes = dag.get("nodes", [])
        edges = dag.get("edges", [])
        certificates: List[GateRejectionCertificate] = []
        tower_layers: List[Sequence[float]] = list(initial_tower_layers or [])

        parents_map: Dict[str, List[str]] = {str(n.get("id", i)): [] for i, n in enumerate(nodes)}
        for edge in edges:
            src = str(edge.get("source", ""))
            dst = str(edge.get("target", ""))
            if dst in parents_map and src in parents_map:
                parents_map[dst].append(src)

        depth_map: Dict[str, int] = {}

        def _get_depth(nid: str, visited: Optional[set] = None) -> int:
            if nid in depth_map:
                return depth_map[nid]
            visited = visited or set()
            if nid in visited:
                return 0
            visited.add(nid)
            preds = parents_map.get(nid, [])
            d = 0 if not preds else 1 + max(_get_depth(p, visited) for p in preds)
            depth_map[nid] = d
            return d

        for nid in parents_map:
            _get_depth(nid)

        wavefronts: Dict[int, List[Dict[str, Any]]] = {}
        for i, node in enumerate(nodes):
            nid = str(node.get("id", i))
            w_idx = depth_map.get(nid, 0)
            wavefronts.setdefault(w_idx, []).append(node)

        for w_idx in sorted(wavefronts.keys()):
            w_nodes = wavefronts[w_idx]
            place_nodes_in_wave = [
                n for n in w_nodes if str(n.get("action", "")).lower() in ("place", "replace_verified")
            ]
            for node in w_nodes:
                others = [n for n in place_nodes_in_wave if n is not node]
                ok, cert = self.validate_proposal(
                    node,
                    tower_layers=tower_layers if str(node.get("action", "")).lower() in ("place", "replace_verified") else None,
                    concurrent_nodes=others if str(node.get("action", "")).lower() in ("place", "replace_verified") else None,
                )
                if not ok and cert is not None:
                    certificates.append(cert)
                elif str(node.get("action", "")).lower() in ("place", "replace_verified"):
                    tower_layers.append([float(node.get("x", 0.0)), float(node.get("y", 0.0)), float(node.get("z", 0.335))])

        return len(certificates) == 0, certificates


class WriteBackPlannerLoop:
    def __init__(self, gate: PreFlightGate, max_retries: int = 3):
        self.gate = gate
        self.max_retries = int(max_retries)
        self.context_window_history: List[str] = []

    def repair_node_deterministically(
        self,
        node: Dict[str, Any],
        cert: GateRejectionCertificate,
        tower_layers: List[Sequence[float]],
        dag_edges: List[Dict[str, Any]],
        peer_nodes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        repaired = copy.deepcopy(node)
        if cert.violation_type == "COM_OVERHANG":
            if tower_layers:
                centroid = np.mean(np.array([layer[:2] for layer in tower_layers], dtype=float), axis=0)
                repaired["x"] = round(float(centroid[0]), 4)
                repaired["y"] = round(float(centroid[1]), 4)
            else:
                repaired["x"] = 0.0
                repaired["y"] = 0.0
        elif cert.violation_type == "IK_OUT_OF_BOUNDS":
            tx = float(repaired.get("x", 0.0))
            ty = float(repaired.get("y", 0.0))
            tz = float(repaired.get("z", 0.335))
            repaired["x"] = round(float(np.clip(tx, -0.12, 0.12)), 4)
            repaired["y"] = round(float(np.clip(ty, -0.12, 0.12)), 4)
            repaired["z"] = round(float(np.clip(tz, 0.30, 0.85)), 4)
        elif cert.violation_type == "SWEPT_VOLUME_COLLISION":
            nid = str(repaired.get("id", repaired.get("node_id", "")))
            for peer in peer_nodes:
                peer_id = str(peer.get("id", peer.get("node_id", "")))
                if peer_id and peer_id != nid:
                    edge_id = f"e_shield_{peer_id}-{nid}"
                    if not any(e.get("source") == peer_id and e.get("target") == nid for e in dag_edges):
                        dag_edges.append({"id": edge_id, "source": peer_id, "target": nid})
                    break
        return repaired

    def validate_and_repair_dag(
        self,
        dag: Dict[str, Any],
        initial_tower_layers: Optional[List[Sequence[float]]] = None,
        repair_callback: Optional[Callable[[Dict[str, Any], GateRejectionCertificate], Dict[str, Any]]] = None,
    ) -> Tuple[Dict[str, Any], List[GateRejectionCertificate], int]:
        working_dag = copy.deepcopy(dag)
        all_certificates: List[GateRejectionCertificate] = []
        retries_used = 0

        for attempt in range(self.max_retries + 1):
            passed, certs = self.gate.validate(working_dag, initial_tower_layers=initial_tower_layers)
            if passed:
                return working_dag, all_certificates, retries_used

            all_certificates.extend(certs)
            if attempt >= self.max_retries:
                break

            retries_used += 1
            self.gate.write_back_iterations += 1
            for cert in certs:
                self.context_window_history.append(cert.to_context_prompt())
                nodes = working_dag.get("nodes", [])
                edges = working_dag.get("edges", [])
                tower_so_far = list(initial_tower_layers or [])
                for idx, n in enumerate(nodes):
                    nid = str(n.get("id", n.get("node_id", idx)))
                    if nid == cert.node_id:
                        if repair_callback is not None:
                            nodes[idx] = repair_callback(n, cert)
                        else:
                            nodes[idx] = self.repair_node_deterministically(
                                n, cert, tower_so_far, edges, nodes
                            )
                        break
                    if str(n.get("action", "")).lower() in ("place", "replace_verified"):
                        tower_so_far.append([float(n.get("x", 0.0)), float(n.get("y", 0.0)), float(n.get("z", 0.335))])

        return working_dag, all_certificates, retries_used
