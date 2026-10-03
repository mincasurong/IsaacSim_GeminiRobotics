"""Structured Experiment Logger for Scientific Evaluation of Multi-Robot VLA Systems.

Captures comprehensive metrics across task planning, robot coordination,
low-level physical execution, and LLM inference for publication-grade benchmarks.
Supports streaming JSONL event traces and aggregated tabular summaries.
"""

import os
import json
import time
import math
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


def compute_gini_coefficient(values: List[float]) -> float:
    """Compute the Gini coefficient of a distribution to measure workload balance.
    
    0.0 represents perfect equality (ideal multi-robot load distribution).
    1.0 represents total inequality (single robot doing all work).
    """
    if not values or all(v == 0 for v in values):
        return 0.0
    n = len(values)
    sorted_vals = sorted(values)
    total = sum(sorted_vals)
    if total == 0:
        return 0.0
    cumulative = 0.0
    sum_diff = 0.0
    for i, val in enumerate(sorted_vals):
        cumulative += val
        sum_diff += (2 * (i + 1) - n - 1) * val
    return float(sum_diff / (n * total))


class ExperimentLogger:
    """Publication-grade logger recording per-event JSONL and trial summaries."""

    def __init__(
        self,
        scenario_id: str,
        trial_num: int = 1,
        goal_text: str = "",
        model_name: str = "gemini-robotics-er-2-preview",
        planner_model: str = "gemini-3.7-flash",
        output_dir: Optional[str] = None
    ):
        self.scenario_id = scenario_id
        self.trial_num = trial_num
        self.goal_text = goal_text
        self.model_name = model_name
        self.planner_model = planner_model

        # Determine log directory
        if output_dir is None:
            # Check environment variable or standard repo locations
            repo_log = os.environ.get("EXPERIMENT_LOG_DIR")
            if repo_log:
                base_dir = Path(repo_log)
            else:
                current_file = Path(__file__).resolve()
                # Try finding repo root
                candidates = [
                    Path("/mnt/d/git/IsaacSim_Gemini/logs/experiments"),
                    Path("d:/git/IsaacSim_Gemini/logs/experiments"),
                    current_file.parents[4] / "logs" / "experiments",
                    Path.home() / ".gemini_robotics" / "logs"
                ]
                base_dir = candidates[0]
                for c in candidates:
                    if c.parent.exists():
                        base_dir = c
                        break
        else:
            base_dir = Path(output_dir)

        self.raw_dir = base_dir / "raw"
        self.summary_dir = base_dir / "summaries"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.summary_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_filename = f"{scenario_id}_trial{trial_num:02d}_{date_str}.jsonl"
        self.log_path = self.raw_dir / self.log_filename

        self._lock = threading.Lock()
        self.start_wall_time = time.time()
        self.start_mono_time = time.monotonic()
        self.end_mono_time: Optional[float] = None

        # Data Accumulators
        self.events: List[Dict[str, Any]] = []
        self.api_calls: List[Dict[str, Any]] = []
        self.brainstorm_turns: List[Dict[str, Any]] = []
        self.actions: List[Dict[str, Any]] = []
        self.replan_count: int = 0
        self.agent_turn_count: int = 0
        self.hallucination_count: int = 0

        # Robot Statistics: FR3_1, FR3_2, FR3_3
        self.robot_stats: Dict[str, Dict[str, Any]] = {
            f"FR3_{i}": {
                "pick_attempts": 0,
                "pick_successes": 0,
                "pick_failures": 0,
                "place_attempts": 0,
                "place_successes": 0,
                "place_failures": 0,
                "total_actions": 0,
                "busy_time_sec": 0.0,
                "busy_pct": 0.0
            }
            for i in (1, 2, 3)
        }

        # Log trial initiation header
        self.log_event("lifecycle", "trial_started", {
            "scenario_id": self.scenario_id,
            "trial_num": self.trial_num,
            "goal_text": self.goal_text,
            "model_name": self.model_name,
            "planner_model": self.planner_model,
            "start_time_iso": datetime.fromtimestamp(self.start_wall_time).isoformat(),
            "log_path": str(self.log_path)
        })

    def _get_elapsed(self) -> float:
        return round(time.monotonic() - self.start_mono_time, 4)

    def log_event(self, category: str, event_type: str, data: Dict[str, Any]):
        """Append a structured timestamped event to the JSONL log stream."""
        record = {
            "t_elapsed": self._get_elapsed(),
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "event": event_type,
            "data": data
        }
        with self._lock:
            self.events.append(record)
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
            except Exception as e:
                print(f"[ExperimentLogger ERROR] Failed to write event: {e}")

    def log_brainstorm_turn(self, role: str, model: str, latency_sec: float, response_length: int):
        """Log a turn in the multi-agent planning brainstorm."""
        turn_data = {
            "role": role,
            "model": model,
            "latency_sec": round(latency_sec, 4),
            "response_length_chars": response_length
        }
        with self._lock:
            self.brainstorm_turns.append(turn_data)
        self.log_event("planning", "brainstorm_turn", turn_data)

    def log_api_call(self, model: str, latency_sec: float, prompt_approx_tokens: int = 0, output_tokens: int = 0, success: bool = True):
        """Record latency and throughput metrics for Gemini API calls."""
        call_data = {
            "model": model,
            "latency_sec": round(latency_sec, 4),
            "prompt_tokens": prompt_approx_tokens,
            "output_tokens": output_tokens,
            "success": success
        }
        with self._lock:
            self.api_calls.append(call_data)
        self.log_event("llm", "api_call", call_data)

    def log_action_dispatched(self, robot_id: str, action: str, target: Optional[str] = None, params: Optional[Dict[str, Any]] = None):
        """Record when a low-level robot action is dispatched to the ROS 2 controller."""
        action_data = {
            "robot": robot_id,
            "action": action,
            "target": target,
            "params": params or {},
            "dispatch_time": self._get_elapsed()
        }
        self.log_event("action", "action_dispatched", action_data)

    def log_action_result(self, robot_id: str, action: str, success: bool, duration_sec: float, message: str = "", target: Optional[str] = None):
        """Record when an action finishes executing on a Franka arm."""
        result_data = {
            "robot": robot_id,
            "action": action,
            "target": target,
            "success": success,
            "duration_sec": round(duration_sec, 4),
            "message": message
        }
        with self._lock:
            self.actions.append(result_data)
            if robot_id in self.robot_stats:
                st = self.robot_stats[robot_id]
                st["total_actions"] += 1
                if action == "pick":
                    st["pick_attempts"] += 1
                    if success:
                        st["pick_successes"] += 1
                    else:
                        st["pick_failures"] += 1
                elif action == "place":
                    st["place_attempts"] += 1
                    if success:
                        st["place_successes"] += 1
                    else:
                        st["place_failures"] += 1

        self.log_event("action", "action_completed", result_data)

    def record_replan(self, reason: str = ""):
        """Increment replanning count."""
        with self._lock:
            self.replan_count += 1
        self.log_event("planning", "replan_triggered", {"replan_count": self.replan_count, "reason": reason})

    def record_agent_turn(self, turn_idx: int, parallel_calls_count: int):
        """Track agent turns in the agentic loop."""
        with self._lock:
            self.agent_turn_count = max(self.agent_turn_count, turn_idx)
        self.log_event("planning", "agent_turn", {
            "turn_index": turn_idx,
            "parallel_calls": parallel_calls_count
        })

    def record_hallucination(self, invalid_reference: str, details: str):
        """Track hallucinated object labels or coordinates outside reachable workspace."""
        with self._lock:
            self.hallucination_count += 1
        self.log_event("planning", "hallucination_detected", {
            "invalid_reference": invalid_reference,
            "details": details,
            "cumulative_hallucinations": self.hallucination_count
        })

    def finalize_trial(
        self,
        task_success: bool,
        blocks_placed: int,
        blocks_target: int,
        tower_stable: bool = True,
        final_tower_height_tf: int = 0,
        mean_displacement_error_m: float = 0.0,
        robot_metrics_live: Optional[Dict[str, Any]] = None,
        exit_status: str = "COMPLETED"
    ) -> Dict[str, Any]:
        """Finalize the trial, compute publication-ready metrics, and write summaries."""
        self.end_mono_time = time.monotonic()
        total_duration = round(self.end_mono_time - self.start_mono_time, 4)

        # Update per-robot metrics from controller if available
        if robot_metrics_live:
            for r_id in ("FR3_1", "FR3_2", "FR3_3"):
                if r_id in robot_metrics_live:
                    r_data = robot_metrics_live[r_id]
                    self.robot_stats[r_id]["busy_pct"] = r_data.get("busy_pct", 0.0)

        # Compute Load Balance Gini coefficient
        action_counts = [self.robot_stats[f"FR3_{i}"]["total_actions"] for i in (1, 2, 3)]
        workload_gini = compute_gini_coefficient([float(x) for x in action_counts])

        # Compute LLM Latencies
        llm_latencies = [c["latency_sec"] for c in self.api_calls if c.get("success", False)]
        avg_llm_latency = float(sum(llm_latencies) / len(llm_latencies)) if llm_latencies else 0.0
        total_planning_time = sum(t["latency_sec"] for t in self.brainstorm_turns)

        # Success Metrics
        gcr = float(blocks_placed / blocks_target) if blocks_target > 0 else 0.0
        pick_attempts_all = sum(self.robot_stats[r]["pick_attempts"] for r in self.robot_stats)
        pick_success_all = sum(self.robot_stats[r]["pick_successes"] for r in self.robot_stats)
        pick_success_rate = float(pick_success_all / pick_attempts_all) if pick_attempts_all > 0 else 0.0

        place_attempts_all = sum(self.robot_stats[r]["place_attempts"] for r in self.robot_stats)
        place_success_all = sum(self.robot_stats[r]["place_successes"] for r in self.robot_stats)
        place_success_rate = float(place_success_all / place_attempts_all) if place_attempts_all > 0 else 0.0

        summary = {
            "scenario_id": self.scenario_id,
            "trial_num": self.trial_num,
            "exit_status": exit_status,
            "task_success": bool(task_success),
            "goal_condition_recall": round(gcr, 4),
            "blocks_placed": blocks_placed,
            "blocks_target": blocks_target,
            "makespan_sec": total_duration,
            "planning_time_sec": round(total_planning_time, 4),
            "execution_time_sec": round(max(0.0, total_duration - total_planning_time), 4),
            "agent_turns_used": self.agent_turn_count,
            "replans_triggered": self.replan_count,
            "hallucinations_detected": self.hallucination_count,
            "workload_gini_coefficient": round(workload_gini, 4),
            "overall_pick_success_rate": round(pick_success_rate, 4),
            "overall_place_success_rate": round(place_success_rate, 4),
            "total_api_calls": len(self.api_calls),
            "avg_api_latency_sec": round(avg_llm_latency, 4),
            "tower_physically_stable": bool(tower_stable),
            "final_tower_height_tf": int(final_tower_height_tf),
            "mean_displacement_error_m": round(mean_displacement_error_m, 4),
            "robot_stats": self.robot_stats
        }

        # Log final summary event
        self.log_event("summary", "trial_completed", summary)

        # Append to CSV summary
        self._append_to_csv_summary(summary)

        return summary

    def _append_to_csv_summary(self, s: Dict[str, Any]):
        """Append trial summary row to aggregated CSV."""
        csv_file = self.summary_dir / f"{self.scenario_id}_summary.csv"
        headers = [
            "scenario_id", "trial_num", "exit_status", "task_success", "gcr",
            "blocks_placed", "blocks_target", "makespan_sec", "planning_time_sec",
            "execution_time_sec", "agent_turns", "replans", "hallucinations",
            "workload_gini", "pick_sr", "place_sr", "api_calls", "avg_api_latency",
            "tower_stable", "final_height_tf", "mean_error_m",
            "r1_actions", "r2_actions", "r3_actions",
            "r1_busy_pct", "r2_busy_pct", "r3_busy_pct"
        ]
        row = [
            s["scenario_id"], s["trial_num"], s["exit_status"], int(s["task_success"]), s["goal_condition_recall"],
            s["blocks_placed"], s["blocks_target"], s["makespan_sec"], s["planning_time_sec"],
            s["execution_time_sec"], s["agent_turns_used"], s["replans_triggered"], s["hallucinations_detected"],
            s["workload_gini_coefficient"], s["overall_pick_success_rate"], s["overall_place_success_rate"],
            s["total_api_calls"], s["avg_api_latency_sec"], int(s["tower_physically_stable"]),
            s["final_tower_height_tf"], s["mean_displacement_error_m"],
            s["robot_stats"]["FR3_1"]["total_actions"],
            s["robot_stats"]["FR3_2"]["total_actions"],
            s["robot_stats"]["FR3_3"]["total_actions"],
            s["robot_stats"]["FR3_1"]["busy_pct"],
            s["robot_stats"]["FR3_2"]["busy_pct"],
            s["robot_stats"]["FR3_3"]["busy_pct"]
        ]
        write_header = not csv_file.exists()
        try:
            with open(csv_file, "a", encoding="utf-8") as f:
                if write_header:
                    f.write(",".join(headers) + "\n")
                f.write(",".join(str(x) for x in row) + "\n")
        except Exception as e:
            print(f"[ExperimentLogger ERROR] Failed writing CSV: {e}")
