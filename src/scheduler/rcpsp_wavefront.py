from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


NOMINAL_SEGMENT_SEC = 0.40


@dataclass
class MutexProfileRecord:
    arm_id: str
    layer: int
    t_wait: float
    t_hold: float
    delta_t_seg: float
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "arm_id": self.arm_id,
            "layer": int(self.layer),
            "t_wait": round(float(self.t_wait), 4),
            "t_hold": round(float(self.t_hold), 4),
            "delta_t_seg": round(float(self.delta_t_seg), 4),
            "timestamp": round(float(self.timestamp), 4),
        }


class MutexProfileStore:
    def __init__(self, nominal_segment_sec: float = NOMINAL_SEGMENT_SEC):
        self.nominal_segment_sec = float(nominal_segment_sec)
        self.records: List[MutexProfileRecord] = []
        self.by_arm_and_layer: Dict[Tuple[str, int], List[MutexProfileRecord]] = {}
        self._active_wait_start: Dict[str, float] = {}
        self._active_grant_start: Dict[str, float] = {}

    @staticmethod
    def normalize_arm_id(arm_id: Any) -> str:
        s = str(arm_id or "fr3_1").strip().lower()
        if s in ("1", "fr3_1", "fr3_arm_1"):
            return "fr3_1"
        if s in ("2", "fr3_2", "fr3_arm_2"):
            return "fr3_2"
        if s in ("3", "fr3_3", "fr3_arm_3"):
            return "fr3_3"
        return s

    def mark_wait_start(self, arm_id: Any, now_mono: float) -> None:
        key = self.normalize_arm_id(arm_id)
        if key not in self._active_wait_start:
            self._active_wait_start[key] = float(now_mono)

    def mark_mutex_acquired(self, arm_id: Any, now_mono: float) -> float:
        key = self.normalize_arm_id(arm_id)
        t_enter = self._active_wait_start.pop(key, float(now_mono))
        t_wait = max(0.0, float(now_mono) - t_enter)
        self._active_grant_start[key] = float(now_mono)
        return t_wait

    def mark_mutex_released(
        self,
        arm_id: Any,
        layer: int,
        now_mono: float,
        actual_segment_sec: Optional[float] = None,
        t_wait_override: Optional[float] = None,
    ) -> MutexProfileRecord:
        key = self.normalize_arm_id(arm_id)
        t_grant = self._active_grant_start.pop(key, float(now_mono) - 1.60)
        t_hold = max(0.05, float(now_mono) - t_grant)
        seg_sec = float(actual_segment_sec) if actual_segment_sec is not None else (t_hold / 4.0)
        delta_t_seg = seg_sec - self.nominal_segment_sec
        t_wait = float(t_wait_override) if t_wait_override is not None else 0.0
        rec = MutexProfileRecord(
            arm_id=key,
            layer=max(1, min(9, int(layer))),
            t_wait=t_wait,
            t_hold=t_hold,
            delta_t_seg=delta_t_seg,
            timestamp=float(now_mono),
        )
        self.record(rec)
        return rec

    def record(self, rec: MutexProfileRecord) -> None:
        arm_key = self.normalize_arm_id(rec.arm_id)
        layer_idx = max(1, min(9, int(rec.layer)))
        normalized = MutexProfileRecord(
            arm_id=arm_key,
            layer=layer_idx,
            t_wait=rec.t_wait,
            t_hold=rec.t_hold,
            delta_t_seg=rec.delta_t_seg,
            timestamp=rec.timestamp,
        )
        self.records.append(normalized)
        self.by_arm_and_layer.setdefault((arm_key, layer_idx), []).append(normalized)

    def get_expected_hold_and_delta(self, arm_id: Any, layer: int) -> Tuple[float, float]:
        arm_key = self.normalize_arm_id(arm_id)
        layer_idx = max(1, min(9, int(layer)))
        bucket = self.by_arm_and_layer.get((arm_key, layer_idx), [])
        if not bucket:
            arm_records = [r for r in self.records if r.arm_id == arm_key]
            if arm_records:
                mean_hold = float(np.mean([r.t_hold for r in arm_records[-5:]]))
                mean_delta = float(np.mean([r.delta_t_seg for r in arm_records[-5:]]))
                return mean_hold, mean_delta
            base_hold = 4.0 * self.nominal_segment_sec + 0.04 * (layer_idx - 1)
            return base_hold, 0.0
        recent = bucket[-5:]
        return (
            float(np.mean([r.t_hold for r in recent])),
            float(np.mean([r.delta_t_seg for r in recent])),
        )

    def to_summary_dict(self) -> Dict[str, Any]:
        table: Dict[str, Any] = {}
        for (arm_key, layer_idx), recs in sorted(self.by_arm_and_layer.items()):
            table[f"{arm_key}_L{layer_idx}"] = {
                "count": len(recs),
                "mean_t_wait": round(float(np.mean([r.t_wait for r in recs])), 4),
                "mean_t_hold": round(float(np.mean([r.t_hold for r in recs])), 4),
                "mean_delta_t_seg": round(float(np.mean([r.delta_t_seg for r in recs])), 4),
            }
        return {
            "total_records": len(self.records),
            "nominal_segment_sec": self.nominal_segment_sec,
            "distributions": table,
        }

    def save_json(self, path: str | Path) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(self.to_summary_dict(), f, indent=2)


@dataclass
class ScheduledNodeWindow:
    node_id: str
    arm_id: str
    action: str
    layer: int
    start_offset_sec: float
    end_offset_sec: float
    mutex_enter_sec: Optional[float] = None
    mutex_exit_sec: Optional[float] = None
    wait_mutex_sec: float = 0.0
    pipelined_pre_positioned: bool = False
    ui_state: str = "STAGED_PRE_GATE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "arm_id": self.arm_id,
            "action": self.action,
            "layer": self.layer,
            "start_offset_sec": round(self.start_offset_sec, 4),
            "end_offset_sec": round(self.end_offset_sec, 4),
            "mutex_enter_sec": round(self.mutex_enter_sec, 4) if self.mutex_enter_sec is not None else None,
            "mutex_exit_sec": round(self.mutex_exit_sec, 4) if self.mutex_exit_sec is not None else None,
            "wait_mutex_sec": round(self.wait_mutex_sec, 4),
            "pipelined_pre_positioned": self.pipelined_pre_positioned,
            "ui_state": self.ui_state,
        }


class ContentionAwareWavefrontScheduler:
    def __init__(
        self,
        mode: str = "rcpsp",
        profile_store: Optional[MutexProfileStore] = None,
        nominal_segment_sec: float = NOMINAL_SEGMENT_SEC,
    ):
        if mode not in ("greedy", "rcpsp"):
            raise ValueError(f"Unsupported scheduler mode '{mode}'. Expected 'greedy' or 'rcpsp'.")
        self.mode = mode
        self.profile_store = profile_store or MutexProfileStore(nominal_segment_sec=nominal_segment_sec)
        self.nominal_segment_sec = float(nominal_segment_sec)

    def _estimate_durations(self, arm_id: str, action: str, layer: int) -> Tuple[float, float]:
        hold_est, delta_seg = self.profile_store.get_expected_hold_and_delta(arm_id, layer)
        seg_sec = max(0.15, self.nominal_segment_sec + delta_seg)
        act = action.lower()
        if act in ("pick", "re_perceive_pose", "regrasp_offset"):
            return 3.0 * seg_sec, 0.0
        if act in ("approach_staging_pose", "stage_pre_gate"):
            return 1.5 * seg_sec, 0.0
        if act in ("place", "replace_verified", "dual_arm_place"):
            pre_gate_sec = 1.5 * seg_sec
            mutex_hold_sec = max(0.8, hold_est)
            return pre_gate_sec, mutex_hold_sec
        return 2.0 * seg_sec, 0.0

    def schedule_dag(self, dag: Dict[str, Any]) -> Dict[str, Any]:
        scheduled_dag = copy.deepcopy(dag)
        nodes = scheduled_dag.get("nodes", [])
        edges = scheduled_dag.get("edges", [])

        parents_map: Dict[str, List[str]] = {str(n.get("id", i)): [] for i, n in enumerate(nodes)}
        for e in edges:
            s = str(e.get("source", ""))
            t = str(e.get("target", ""))
            if t in parents_map and s in parents_map:
                parents_map[t].append(s)

        arm_free_at: Dict[str, float] = {"fr3_1": 0.0, "fr3_2": 0.0, "fr3_3": 0.0}
        node_end_at: Dict[str, float] = {}
        mutex_free_at: float = 0.0
        windows: List[ScheduledNodeWindow] = []
        mutex_reservations: List[Dict[str, Any]] = []

        unscheduled = list(nodes)
        layer_counter = 0

        while unscheduled:
            ready = [
                n
                for n in unscheduled
                if all(p in node_end_at for p in parents_map.get(str(n.get("id", "")), []))
            ]
            if not ready:
                ready = [unscheduled[0]]

            if self.mode == "rcpsp":
                def _priority_key(n: Dict[str, Any]) -> Tuple[int, float, str]:
                    act = str(n.get("action", "pick")).lower()
                    arm_k = self.profile_store.normalize_arm_id(n.get("robot", n.get("arm_id", "fr3_1")))
                    preds = parents_map.get(str(n.get("id", "")), [])
                    dep_ready = max([node_end_at[p] for p in preds], default=0.0)
                    earliest_arm = max(arm_free_at.get(arm_k, 0.0), dep_ready)
                    is_place = 1 if act in ("place", "replace_verified", "dual_arm_place") else 0
                    return (is_place, earliest_arm, str(n.get("id", "")))

                ready.sort(key=_priority_key)

            for n in ready:
                nid = str(n.get("id", ""))
                arm_k = self.profile_store.normalize_arm_id(n.get("robot", n.get("arm_id", "fr3_1")))
                act = str(n.get("action", "pick")).lower()
                preds = parents_map.get(nid, [])
                dep_ready = max([node_end_at[p] for p in preds], default=0.0)
                arm_ready = max(arm_free_at.get(arm_k, 0.0), dep_ready)

                if act in ("place", "replace_verified", "dual_arm_place"):
                    layer_counter += 1
                layer_idx = int(n.get("layer", max(1, layer_counter)))
                pre_sec, mutex_sec = self._estimate_durations(arm_k, act, layer_idx)

                if act in ("place", "replace_verified", "dual_arm_place"):
                    if self.mode == "greedy":
                        arrival_at_gate = arm_ready
                        mutex_enter = max(arrival_at_gate, mutex_free_at)
                        wait_time = max(0.0, mutex_enter - arrival_at_gate)
                        effective_hold = mutex_sec + pre_sec
                        mutex_exit = mutex_enter + effective_hold
                        start_offset = arrival_at_gate
                        end_offset = mutex_exit
                        pipelined = False
                        ui_state = "WAITING_MUTEX" if wait_time > 1e-3 else "EXECUTING"
                    else:
                        earliest_gate_arrival = arm_ready + pre_sec
                        mutex_enter = max(earliest_gate_arrival, mutex_free_at)
                        start_offset = max(arm_ready, mutex_enter - pre_sec)
                        arrival_at_gate = start_offset + pre_sec
                        wait_time = max(0.0, mutex_enter - arrival_at_gate)
                        mutex_exit = mutex_enter + mutex_sec
                        end_offset = mutex_exit
                        pipelined = True
                        ui_state = "STAGED_PRE_GATE"

                    mutex_free_at = mutex_exit
                    mutex_reservations.append(
                        {
                            "node_id": nid,
                            "arm_id": arm_k,
                            "layer": layer_idx,
                            "enter_sec": round(mutex_enter, 4),
                            "exit_sec": round(mutex_exit, 4),
                            "wait_sec": round(wait_time, 4),
                        }
                    )
                    win = ScheduledNodeWindow(
                        node_id=nid,
                        arm_id=arm_k,
                        action=act,
                        layer=layer_idx,
                        start_offset_sec=start_offset,
                        end_offset_sec=end_offset,
                        mutex_enter_sec=mutex_enter,
                        mutex_exit_sec=mutex_exit,
                        wait_mutex_sec=wait_time,
                        pipelined_pre_positioned=pipelined,
                        ui_state=ui_state,
                    )
                else:
                    start_offset = arm_ready
                    end_offset = start_offset + pre_sec
                    win = ScheduledNodeWindow(
                        node_id=nid,
                        arm_id=arm_k,
                        action=act,
                        layer=max(1, layer_idx),
                        start_offset_sec=start_offset,
                        end_offset_sec=end_offset,
                        mutex_enter_sec=None,
                        mutex_exit_sec=None,
                        wait_mutex_sec=0.0,
                        pipelined_pre_positioned=(self.mode == "rcpsp"),
                        ui_state="EXECUTING",
                    )

                arm_free_at[arm_k] = end_offset
                node_end_at[nid] = end_offset
                n["start_offset_sec"] = round(win.start_offset_sec, 4)
                n["end_offset_sec"] = round(win.end_offset_sec, 4)
                n["wait_mutex_sec"] = round(win.wait_mutex_sec, 4)
                n["ui_state"] = win.ui_state
                windows.append(win)
                unscheduled.remove(n)

        makespan_sec = max(node_end_at.values(), default=0.0)
        total_mutex_wait = sum(w.wait_mutex_sec for w in windows)
        total_arm_busy = sum(w.end_offset_sec - w.start_offset_sec - w.wait_mutex_sec for w in windows)
        arm_utilization_pct = (
            (total_arm_busy / (3.0 * makespan_sec)) * 100.0 if makespan_sec > 1e-6 else 0.0
        )

        sorted_res = sorted(mutex_reservations, key=lambda r: r["enter_sec"])
        mutex_violations = 0
        for idx in range(len(sorted_res) - 1):
            if sorted_res[idx]["exit_sec"] > sorted_res[idx + 1]["enter_sec"] + 1e-6:
                mutex_violations += 1

        scheduled_dag["schedule"] = {
            "scheduler_mode": self.mode,
            "makespan_sec": round(makespan_sec, 4),
            "mutex_wait_time_total_sec": round(total_mutex_wait, 4),
            "mean_mutex_wait_sec": round(total_mutex_wait / max(1, len(mutex_reservations)), 4),
            "arm_utilization_pct": round(arm_utilization_pct, 2),
            "mutex_violations": mutex_violations,
            "windows": [w.to_dict() for w in windows],
            "mutex_reservations": sorted_res,
        }
        return scheduled_dag

    def write_back_layer_timing(
        self,
        dag: Dict[str, Any],
        completed_layer: int,
        arm_id: str,
        measured_t_hold: float,
        measured_delta_t_seg: float,
        measured_t_wait: float = 0.0,
    ) -> Dict[str, Any]:
        self.profile_store.record(
            MutexProfileRecord(
                arm_id=arm_id,
                layer=completed_layer,
                t_wait=measured_t_wait,
                t_hold=measured_t_hold,
                delta_t_seg=measured_delta_t_seg,
            )
        )
        return self.schedule_dag(dag)
