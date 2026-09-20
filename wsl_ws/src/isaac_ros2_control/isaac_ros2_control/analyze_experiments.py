"""Scientific Analysis and Visualization Script for Multi-Robot VLA Benchmark Experiments.

Processes raw JSONL event streams and CSV summaries to generate publication-ready
LaTeX tables (.tex) and high-resolution vector figures (.pdf, .png) for arXiv/conference papers.
"""

import os
import sys
import json
import glob
import math
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import numpy as np

# Try importing matplotlib, provide graceful fallback
try:
    import matplotlib
    matplotlib.use('Agg')  # Headless backend
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def wilson_score_interval(successes: int, total: int, confidence: float = 0.95) -> Tuple[float, float, float]:
    """Compute Wilson score interval for binomial proportion confidence interval.
    
    Standard in robotics benchmarking to report rigorous success rates with small sample sizes.
    Returns: (point_estimate, lower_bound, upper_bound)
    """
    if total == 0:
        return 0.0, 0.0, 0.0
    p = successes / total
    z = 1.95996  # 95% confidence standard normal quantile
    z2 = z * z
    denominator = 1 + z2 / total
    centre_adjusted_probability = p + z2 / (2 * total)
    adjusted_std_dev = math.sqrt((p * (1 - p) + z2 / (4 * total)) / total)
    lower = (centre_adjusted_probability - z * adjusted_std_dev) / denominator
    upper = (centre_adjusted_probability + z * adjusted_std_dev) / denominator
    return p, max(0.0, lower), min(1.0, upper)


class ExperimentAnalyzer:
    """Parses experiment logs and produces publication tables and figures."""

    def __init__(self, log_dir: str, output_dir: Optional[str] = None):
        self.log_dir = Path(log_dir)
        self.raw_dir = self.log_dir / "raw"
        self.summary_dir = self.log_dir / "summaries"

        if output_dir:
            self.out_dir = Path(output_dir)
        else:
            self.out_dir = self.log_dir

        self.tables_dir = self.out_dir / "tables"
        self.figures_dir = self.out_dir / "figures"
        self.tables_dir.mkdir(parents=True, exist_ok=True)
        self.figures_dir.mkdir(parents=True, exist_ok=True)

        self.trials: List[Dict[str, Any]] = []
        self._load_trials()

    def _load_trials(self):
        """Load trial summary data from all JSONL raw logs or CSV files."""
        # Check raw JSONL files first
        jsonl_files = list(self.raw_dir.glob("*.jsonl"))
        for jf in jsonl_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in reversed(lines):
                        record = json.loads(line.strip())
                        if record.get("event") == "trial_completed":
                            self.trials.append(record["data"])
                            break
            except Exception as e:
                print(f"[WARN] Error reading {jf}: {e}")

        print(f"[INFO] Loaded {len(self.trials)} trial summaries from {self.raw_dir}")

    def generate_latex_table1_success_rate(self) -> str:
        """Generate Table 1: Task Success Rate & Goal Condition Recall with 95% Wilson CI."""
        scenarios = sorted(list(set(t["scenario_id"] for t in self.trials)))
        lines = [
            r"\begin{table}[t]",
            r"\centering",
            r"\caption{Task Success Rate (TSR) and Goal Condition Recall (GCR) across Benchmark Scenarios (95\% Wilson Confidence Intervals).}",
            r"\label{tab:task_success}",
            r"\begin{tabular}{lcccccc}",
            r"\toprule",
            r"\textbf{Scenario ID} & \textbf{Trials} & \textbf{Successes} & \textbf{TSR (\%)} & \textbf{95\% CI} & \textbf{Mean GCR} & \textbf{Final Height} \\",
            r"\midrule"
        ]

        for sc in scenarios:
            sc_trials = [t for t in self.trials if t["scenario_id"] == sc]
            n = len(sc_trials)
            succ = sum(1 for t in sc_trials if t.get("task_success", False))
            p, low, high = wilson_score_interval(succ, n)
            gcrs = [t.get("goal_condition_recall", 0.0) for t in sc_trials]
            mean_gcr = float(np.mean(gcrs)) if gcrs else 0.0
            heights = [t.get("final_tower_height_tf", 0) for t in sc_trials]
            mean_h = float(np.mean(heights)) if heights else 0.0

            ci_str = f"[{low*100:.1f}, {high*100:.1f}]"
            lines.append(f"{sc} & {n} & {succ} & {p*100:.1f}\\% & {ci_str} & {mean_gcr*100:.1f}\\% & {mean_h:.1f} \\\\")

        lines.extend([
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}"
        ])
        tex = "\n".join(lines)
        out_path = self.tables_dir / "table1_success_rate.tex"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(tex)
        print(f"[SAVED] {out_path}")
        return tex

    def generate_latex_table2_timing_breakdown(self) -> str:
        """Generate Table 2: Wall-Clock Timing Breakdown (Planning vs Execution)."""
        scenarios = sorted(list(set(t["scenario_id"] for t in self.trials)))
        lines = [
            r"\begin{table}[t]",
            r"\centering",
            r"\caption{Wall-Clock Timing Breakdown: Brainstorming Planning Latency vs. Physical Robot Execution Duration (Mean $\pm$ Std).}",
            r"\label{tab:timing_breakdown}",
            r"\begin{tabular}{lcccc}",
            r"\toprule",
            r"\textbf{Scenario} & \textbf{Planning Time (s)} & \textbf{Execution Time (s)} & \textbf{Makespan (s)} & \textbf{Agent Turns} \\",
            r"\midrule"
        ]

        for sc in scenarios:
            sc_trials = [t for t in self.trials if t["scenario_id"] == sc]
            plan_times = [t.get("planning_time_sec", 0.0) for t in sc_trials]
            exec_times = [t.get("execution_time_sec", 0.0) for t in sc_trials]
            makespans = [t.get("makespan_sec", 0.0) for t in sc_trials]
            turns = [t.get("agent_turns_used", 0) for t in sc_trials]

            p_m, p_s = np.mean(plan_times), np.std(plan_times)
            e_m, e_s = np.mean(exec_times), np.std(exec_times)
            m_m, m_s = np.mean(makespans), np.std(makespans)
            t_m, t_s = np.mean(turns), np.std(turns)

            lines.append(f"{sc} & ${p_m:.1f} \\pm {p_s:.1f}$ & ${e_m:.1f} \\pm {e_s:.1f}$ & ${m_m:.1f} \\pm {m_s:.1f}$ & ${t_m:.1f} \\pm {t_s:.1f}$ \\\\")

        lines.extend([
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}"
        ])
        tex = "\n".join(lines)
        out_path = self.tables_dir / "table2_timing_breakdown.tex"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(tex)
        print(f"[SAVED] {out_path}")
        return tex

    def generate_latex_table3_robot_coordination(self) -> str:
        """Generate Table 3: Multi-Robot Workload Distribution & Physical Grasp Quality."""
        scenarios = sorted(list(set(t["scenario_id"] for t in self.trials)))
        lines = [
            r"\begin{table}[t]",
            r"\centering",
            r"\caption{Multi-Robot Workload Distribution, Gini Balance Coefficient, and Low-Level Action Success Rates.}",
            r"\label{tab:robot_coordination}",
            r"\begin{tabular}{lccccc}",
            r"\toprule",
            r"\textbf{Scenario} & \textbf{Workload Gini} & \textbf{Pick SR (\%)} & \textbf{Place SR (\%)} & \textbf{Replans} & \textbf{Mean Error (m)} \\",
            r"\midrule"
        ]

        for sc in scenarios:
            sc_trials = [t for t in self.trials if t["scenario_id"] == sc]
            ginis = [t.get("workload_gini_coefficient", 0.0) for t in sc_trials]
            pick_srs = [t.get("overall_pick_success_rate", 0.0) * 100 for t in sc_trials]
            place_srs = [t.get("overall_place_success_rate", 0.0) * 100 for t in sc_trials]
            replans = [t.get("replans_triggered", 0) for t in sc_trials]
            errors = [t.get("mean_displacement_error_m", 0.0) for t in sc_trials]

            lines.append(
                f"{sc} & ${np.mean(ginis):.3f} \\pm {np.std(ginis):.2f}$ & "
                f"${np.mean(pick_srs):.1f}\\%$ & ${np.mean(place_srs):.1f}\\%$ & "
                f"${np.mean(replans):.1f}$ & ${np.mean(errors):.3f} \\pm {np.std(errors):.3f}$ \\\\"
            )

        lines.extend([
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}"
        ])
        tex = "\n".join(lines)
        out_path = self.tables_dir / "table3_robot_coordination.tex"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(tex)
        print(f"[SAVED] {out_path}")
        return tex

    def plot_figure2_success_rates(self):
        """Plot Figure 2: Task Success Rate bar chart across benchmark tiers."""
        if not HAS_MPL or not self.trials:
            return

        scenarios = sorted(list(set(t["scenario_id"] for t in self.trials)))
        labels = []
        rates = []
        err_low = []
        err_high = []

        for sc in scenarios:
            sc_trials = [t for t in self.trials if t["scenario_id"] == sc]
            n = len(sc_trials)
            succ = sum(1 for t in sc_trials if t.get("task_success", False))
            p, low, high = wilson_score_interval(succ, n)
            labels.append(sc)
            rates.append(p * 100)
            err_low.append((p - low) * 100)
            err_high.append((high - p) * 100)

        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
        x = np.arange(len(labels))
        bars = ax.bar(x, rates, yerr=[err_low, err_high], capsize=5, color="#3b82f6", edgecolor="#1d4ed8", alpha=0.85, width=0.55)

        ax.set_ylabel("Task Success Rate (%)", fontsize=12, fontweight="bold")
        ax.set_xlabel("Benchmark Scenario Tier", fontsize=12, fontweight="bold")
        ax.set_title("Multi-Robot VLA Autonomous Task Success Rate (95% Wilson CI)", fontsize=13, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=11)
        ax.set_ylim(0, 105)
        ax.grid(axis='y', linestyle='--', alpha=0.5)

        for bar in bars:
            h = bar.get_height()
            ax.annotate(f"{h:.1f}%",
                        xy=(bar.get_x() + bar.get_width() / 2, h),
                        xytext=(0, 6), textcoords="offset points",
                        ha='center', va='bottom', fontsize=9, fontweight='bold')

        plt.tight_layout()
        pdf_path = self.figures_dir / "fig2_success_rate.pdf"
        png_path = self.figures_dir / "fig2_success_rate.png"
        plt.savefig(pdf_path)
        plt.savefig(png_path)
        plt.close()
        print(f"[SAVED] {pdf_path} and {png_path}")

    def plot_figure3_utilization_breakdown(self):
        """Plot Figure 3: Robot workload balance across FR3_1, FR3_2, FR3_3."""
        if not HAS_MPL or not self.trials:
            return

        scenarios = sorted(list(set(t["scenario_id"] for t in self.trials)))
        r1_actions = []
        r2_actions = []
        r3_actions = []

        for sc in scenarios:
            sc_trials = [t for t in self.trials if t["scenario_id"] == sc]
            r1 = [t["robot_stats"]["FR3_1"]["total_actions"] for t in sc_trials]
            r2 = [t["robot_stats"]["FR3_2"]["total_actions"] for t in sc_trials]
            r3 = [t["robot_stats"]["FR3_3"]["total_actions"] for t in sc_trials]
            r1_actions.append(float(np.mean(r1)))
            r2_actions.append(float(np.mean(r2)))
            r3_actions.append(float(np.mean(r3)))

        fig, ax = plt.subplots(figsize=(9, 4.8), dpi=300)
        x = np.arange(len(scenarios))
        width = 0.25

        ax.bar(x - width, r1_actions, width, label="FR3_1 (Arm 1)", color="#ef4444", alpha=0.85)
        ax.bar(x, r2_actions, width, label="FR3_2 (Arm 2)", color="#10b981", alpha=0.85)
        ax.bar(x + width, r3_actions, width, label="FR3_3 (Arm 3)", color="#3b82f6", alpha=0.85)

        ax.set_ylabel("Mean Actions Executed", fontsize=12, fontweight="bold")
        ax.set_title("Multi-Robot Team Workload Distribution per Scenario", fontsize=13, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(scenarios, fontsize=11)
        ax.legend(frameon=True)
        ax.grid(axis='y', linestyle='--', alpha=0.5)

        plt.tight_layout()
        pdf_path = self.figures_dir / "fig3_utilization_heatmap.pdf"
        plt.savefig(pdf_path)
        plt.close()
        print(f"[SAVED] {pdf_path}")

    def run_full_analysis(self):
        """Execute all analysis and figure generation pipelines."""
        if not self.trials:
            print("[WARN] No trial data found to analyze. Run experiments first!")
            return

        print("\n--- Generating Publication Tables ---")
        self.generate_latex_table1_success_rate()
        self.generate_latex_table2_timing_breakdown()
        self.generate_latex_table3_robot_coordination()

        print("\n--- Generating Publication Figures ---")
        self.plot_figure2_success_rates()
        self.plot_figure3_utilization_breakdown()
        print("\n[SUCCESS] Scientific evaluation analysis complete!")


def main():
    parser = argparse.ArgumentParser(description="Analyze Multi-Robot VLA Experiment Logs")
    parser.add_argument("--log-dir", type=str, default="/mnt/d/git/IsaacSim_Gemini/logs/experiments", help="Path to experiment log directory")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory for generated tables and figures")
    args = parser.parse_args()

    # Fallback to local repo path if running on Windows
    log_path = Path(args.log_dir)
    if not log_path.exists():
        candidates = [
            Path("d:/git/IsaacSim_Gemini/logs/experiments"),
            Path(__file__).resolve().parents[4] / "logs" / "experiments"
        ]
        for c in candidates:
            if c.exists():
                log_path = c
                break

    analyzer = ExperimentAnalyzer(log_dir=str(log_path), output_dir=args.output_dir)
    analyzer.run_full_analysis()


if __name__ == '__main__':
    main()
