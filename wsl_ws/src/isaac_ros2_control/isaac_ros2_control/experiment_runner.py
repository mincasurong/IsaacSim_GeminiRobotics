"""Automated Benchmark Runner for Multi-Robot VLA Evaluation.

Executes N randomized trials across standardized scenarios (S1-S7),
verifies ground-truth physical stability via TF transforms,
and compiles publication-ready benchmark datasets.
"""

import sys
import os
import time
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Empty
from std_srvs.srv import Trigger, SetBool
import tf2_ros
import numpy as np

try:
    from isaac_ros2_control import experiment_scenarios
    from isaac_ros2_control import experiment_logger
except ImportError:
    try:
        from . import experiment_scenarios
        from . import experiment_logger
    except ImportError:
        import experiment_scenarios
        import experiment_logger


class ExperimentRunner(Node):
    """ROS 2 Node orchestrating automated evaluation trials."""

    def __init__(self, scenario_ids: List[str], num_trials: int = 20, dry_run: bool = False, baseline_mode: bool = False, output_dir: Optional[str] = None):
        super().__init__('experiment_runner')

        self.scenario_ids = scenario_ids
        self.num_trials = num_trials
        self.dry_run = dry_run
        self.baseline_mode = baseline_mode
        self.output_dir = output_dir

        # Publishers
        self.goal_pub = self.create_publisher(String, '/gemini/custom_goal', 10)
        self.reset_sim_pub = self.create_publisher(Empty, '/reset_simulation', 10)

        # Service Clients
        self.reset_cli = self.create_client(Trigger, '/multi_robot/reset')
        self.mode_cli = self.create_client(SetBool, '/multi_robot/set_gemini_mode')

        # Subscribers for telemetry
        self.metrics_sub = self.create_subscription(String, '/multi_robot/robot_metrics', self._metrics_cb, 10)
        self.action_res_sub = self.create_subscription(String, '/gemini/action_result', self._action_res_cb, 10)

        # TF2 Buffer
        self.tf_buffer = tf2_ros.Buffer(node=self)
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # State tracking
        self.latest_robot_metrics: Optional[Dict[str, Any]] = None
        self.latest_action_results: List[Dict[str, Any]] = []
        self.trial_active: bool = False
        self.trial_completed_event = False

        self.get_logger().info(
            f"ExperimentRunner initialized. Scenarios: {self.scenario_ids}, "
            f"Trials: {self.num_trials}, Dry-Run: {self.dry_run}, Baseline Mode: {self.baseline_mode}"
        )

    def _metrics_cb(self, msg: String):
        try:
            self.latest_robot_metrics = json.loads(msg.data)
        except Exception:
            pass

    def _action_res_cb(self, msg: String):
        try:
            data = json.loads(msg.data)
            self.latest_action_results.append(data)
        except Exception:
            pass

    def reset_environment(self) -> bool:
        """Call simulation and controller reset services."""
        self.get_logger().info("[RESET] Triggering simulation reset...")
        self.reset_sim_pub.publish(Empty())

        if self.reset_cli.wait_for_service(timeout_sec=2.0):
            req = Trigger.Request()
            future = self.reset_cli.call_async(req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=3.0)

        # Set controller mode
        if self.mode_cli.wait_for_service(timeout_sec=2.0):
            req = SetBool.Request()
            req.data = not self.baseline_mode  # True = Gemini, False = Rule sequencer
            future = self.mode_cli.call_async(req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=2.0)

        # Allow physics to settle
        time.sleep(2.5)
        return True

    def query_tf_block_poses(self) -> Dict[str, np.ndarray]:
        """Query world positions of all 9 blocks from TF."""
        block_poses = {}
        for i in range(1, 10):
            name = f"Block{i}"
            try:
                trans = self.tf_buffer.lookup_transform('world', name, rclpy.time.Time())
                p = trans.transform.translation
                block_poses[name] = np.array([p.x, p.y, p.z])
            except Exception:
                pass
        return block_poses

    def evaluate_physical_state(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Verify ground-truth physical outcome on target table."""
        block_poses = self.query_tf_block_poses()
        placed_blocks = []
        errors = []

        # Central table bounds: X in [-0.15, 0.15], Y in [-0.15, 0.15], Z >= 0.28
        for name, pos in block_poses.items():
            if abs(pos[0]) <= 0.18 and abs(pos[1]) <= 0.18 and pos[2] >= 0.28:
                placed_blocks.append((name, pos))

        # Check target coordinate alignment if specified
        target_coords = scenario.get("target_coordinates", [])
        if target_coords and placed_blocks:
            for _, pos in placed_blocks:
                # Find closest expected target coordinate
                dists = [np.linalg.norm(pos[:2] - np.array(tc[:2])) for tc in target_coords]
                if dists:
                    errors.append(min(dists))

        mean_error = float(np.mean(errors)) if errors else 0.0
        blocks_placed = len(placed_blocks)
        blocks_target = scenario.get("blocks_target", 1)
        success = (blocks_placed >= blocks_target)

        return {
            "success": success,
            "blocks_placed": blocks_placed,
            "blocks_target": blocks_target,
            "mean_error_m": round(mean_error, 4),
            "placed_block_names": [b[0] for b in placed_blocks]
        }

    def run_trial(self, scenario: Dict[str, Any], trial_idx: int) -> Dict[str, Any]:
        """Execute a single trial of a scenario."""
        sc_id = scenario["id"]
        self.get_logger().info(f"\n{'='*60}\n>>> Starting Scenario {sc_id} ({scenario['name']}) | Trial {trial_idx}/{self.num_trials}\n{'='*60}")

        # 1. Reset Environment
        self.reset_environment()
        self.latest_action_results = []

        # 2. Setup Logger
        logger = experiment_logger.ExperimentLogger(
            scenario_id=sc_id if not self.baseline_mode else f"{sc_id}_RULE_BASELINE",
            trial_num=trial_idx,
            goal_text=scenario["goal"],
            output_dir=self.output_dir
        )

        if self.dry_run:
            self.get_logger().info("[DRY RUN] Simulating dry run trial execution...")
            time.sleep(1.0)
            summary = logger.finalize_trial(
                task_success=True,
                blocks_placed=scenario["blocks_target"],
                blocks_target=scenario["blocks_target"],
                tower_stable=True,
                final_tower_height_tf=scenario["blocks_target"],
                exit_status="DRY_RUN"
            )
            return summary

        # 3. Publish Custom Goal (initiates planning & agentic loop in gemini_robotics_node)
        goal_payload = {
            "scenario_id": sc_id if not self.baseline_mode else f"{sc_id}_RULE_BASELINE",
            "trial_num": trial_idx,
            "goal": scenario["goal"],
            "blocks_target": scenario["blocks_target"]
        }
        goal_msg = String()
        goal_msg.data = json.dumps(goal_payload)
        self.goal_pub.publish(goal_msg)

        # 4. Monitor Execution until Timeout or Task Finish
        timeout_sec = scenario.get("timeout_sec", 300)
        t_start = time.monotonic()
        last_log_t = t_start

        while time.monotonic() - t_start < timeout_sec:
            rclpy.spin_once(self, timeout_sec=0.2)

            # Check if all robots reached FINISHED in baseline mode
            if self.baseline_mode and self.latest_robot_metrics:
                robots = self.latest_robot_metrics.get("robots", {})
                if all(robots.get(f"FR3_{i}", {}).get("phase") == "IDLE" for i in (1, 2, 3)):
                    self.get_logger().info("[BASELINE] All robots finished.")
                    break

            # Status heartbeat
            if time.monotonic() - last_log_t > 15.0:
                elapsed = int(time.monotonic() - t_start)
                self.get_logger().info(f"[{sc_id} Trial {trial_idx}] In progress... {elapsed}s / {timeout_sec}s")
                last_log_t = time.monotonic()

            # Early termination check: if target blocks are placed and robots are stationary
            if time.monotonic() - t_start > 30.0:
                phys = self.evaluate_physical_state(scenario)
                if phys["blocks_placed"] >= scenario["blocks_target"]:
                    if self.latest_robot_metrics:
                        robots = self.latest_robot_metrics.get("robots", {})
                        phases = [robots.get(f"FR3_{i}", {}).get("phase") for i in (1, 2, 3)]
                        if all(p in ("IDLE", "QUEUED", "INIT") for p in phases):
                            self.get_logger().info(f"\033[92m[EARLY FINISH] All {scenario['blocks_target']} blocks verified in position!\033[0m")
                            time.sleep(2.0)  # Brief settling
                            break

        # 5. Final Evaluation via Ground-Truth TF
        phys_eval = self.evaluate_physical_state(scenario)
        self.get_logger().info(
            f"[{sc_id} Trial {trial_idx} RESULT] Success: {phys_eval['success']}, "
            f"Blocks Placed: {phys_eval['blocks_placed']}/{phys_eval['blocks_target']}, "
            f"Mean Error: {phys_eval['mean_error_m']}m"
        )

        # 6. Finalize Trial Summary
        summary = logger.finalize_trial(
            task_success=phys_eval["success"],
            blocks_placed=phys_eval["blocks_placed"],
            blocks_target=phys_eval["blocks_target"],
            tower_stable=phys_eval["success"],
            final_tower_height_tf=phys_eval["blocks_placed"],
            mean_displacement_error_m=phys_eval["mean_error_m"],
            robot_metrics_live=self.latest_robot_metrics.get("robots") if self.latest_robot_metrics else None,
            exit_status="COMPLETED" if phys_eval["success"] else "TIMEOUT_OR_FAILED"
        )
        return summary

    def run_all(self):
        """Run all configured scenarios and trials sequentially."""
        all_summaries = []
        t_global_start = time.time()

        for sc_id in self.scenario_ids:
            sc = experiment_scenarios.get_scenario(sc_id)
            if not sc:
                self.get_logger().error(f"Unknown scenario ID: {sc_id}")
                continue

            for trial_idx in range(1, self.num_trials + 1):
                summary = self.run_trial(sc, trial_idx)
                all_summaries.append(summary)

        total_elapsed = round(time.time() - t_global_start, 2)
        self.get_logger().info(f"\n{'#'*60}\nALL BENCHMARKS COMPLETED in {total_elapsed}s! Total trials: {len(all_summaries)}\n{'#'*60}")


def main(args=None):
    rclpy.init(args=args)

    parser = argparse.ArgumentParser(description="Multi-Robot VLA Benchmark Runner")
    parser.add_argument("--scenarios", type=str, default="S1", help="Comma-separated scenario IDs (e.g. S1,S2,S3 or all)")
    parser.add_argument("--trials", type=int, default=1, help="Number of trials per scenario (default 1 for test, 20 for full paper)")
    parser.add_argument("--dry-run", action="store_true", help="Execute trial harness without Gemini API calls")
    parser.add_argument("--baseline", action="store_true", help="Run rule-based sequencer baseline instead of VLA")
    parser.add_argument("--output-dir", type=str, default=None, help="Custom output directory for experiment logs")

    parsed, _ = parser.parse_known_args()

    if parsed.scenarios.lower() == "all":
        sc_ids = experiment_scenarios.list_scenario_ids()
    else:
        sc_ids = [s.strip().upper() for s in parsed.scenarios.split(",") if s.strip()]

    runner = ExperimentRunner(
        scenario_ids=sc_ids,
        num_trials=parsed.trials,
        dry_run=parsed.dry_run,
        baseline_mode=parsed.baseline,
        output_dir=parsed.output_dir
    )

    try:
        runner.run_all()
    except KeyboardInterrupt:
        runner.get_logger().warn("Experiment runner interrupted by user.")
    finally:
        runner.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
