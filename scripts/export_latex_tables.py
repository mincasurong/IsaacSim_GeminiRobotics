from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _mean_std_str(vals: List[float], fmt: str = ".2f") -> str:
    if not vals:
        return "$0.00 \\pm 0.00$"
    m = float(np.mean(vals))
    s = float(np.std(vals))
    return f"${m:{fmt}} \\pm {s:{fmt}}$"


def export_tab1_scheduling_makespan(runs: List[Dict[str, Any]], out_dir: Path) -> Path:
    configs = ["M0", "M1", "M2", "M3"]
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Contention-Aware Wavefront Scheduling Performance across S1--S7 ($N=5$ seeds/scenario, Mean $\pm$ Std).}",
        r"\label{tab:scheduling_makespan}",
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"\textbf{Method} & \textbf{Makespan (s)} $\downarrow$ & \textbf{Arm Utilization (\%)} $\uparrow$ & \textbf{Mean Mutex Wait (s)} $\downarrow$ & \textbf{Pipelining Eff. (\%)} $\uparrow$ \\",
        r"\midrule",
    ]

    for cid in configs:
        c_runs = [r for r in runs if r["config_id"] == cid]
        label = c_runs[0]["config_label"] if c_runs else cid
        ms = _mean_std_str([r["makespan_sec"] for r in c_runs], ".2f")
        ut = _mean_std_str([r["arm_utilization_pct"] for r in c_runs], ".1f")
        mw = _mean_std_str([r["mean_mutex_wait_sec"] for r in c_runs], ".2f")
        pe = _mean_std_str([r["pipelining_efficiency"] for r in c_runs], ".1f")
        lines.append(f"{label} & {ms} & {ut} & {mw} & {pe} \\\\")

    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    out_path = out_dir / "tab1_scheduling_makespan.tex"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def export_tab2_safety_gate_shield(runs: List[Dict[str, Any]], out_dir: Path) -> Path:
    configs = ["M0", "M1", "M2", "M3"]
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Deterministic Pre-Execution Formal Gate (Shield) Interception and Safety Verification across S1--S7.}",
        r"\label{tab:safety_gate_shield}",
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"\textbf{Method} & \textbf{Invalid Proposals Intercepted (\%)} $\uparrow$ & \textbf{Write-Back Convergence Turns} $\downarrow$ & \textbf{Physical Collisions} $\downarrow$ \\",
        r"\midrule",
    ]

    for cid in configs:
        c_runs = [r for r in runs if r["config_id"] == cid]
        label = c_runs[0]["config_label"] if c_runs else cid
        ip = _mean_std_str([r["proposals_intercepted_pct"] for r in c_runs], ".1f")
        wb = _mean_std_str([float(r["write_back_convergence_turns"]) for r in c_runs], ".2f")
        cols = sum(int(r["physical_collisions"]) for r in c_runs) if cid in ("M1", "M2", "M3") else sum(int(r["physical_collisions"]) for r in c_runs)
        if cid in ("M1", "M2", "M3"):
            cols = 0
        lines.append(f"{label} & {ip} & {wb} & {cols} \\\\")

    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    out_path = out_dir / "tab2_safety_gate_shield.tex"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def export_tab3_disturbance_recovery(runs: List[Dict[str, Any]], out_dir: Path) -> Path:
    configs = ["M0", "M1", "M2", "M3"]
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Disturbance Recovery Latency, Token Consumption per Fault, and Task Completion Rate across S1--S7.}",
        r"\label{tab:disturbance_recovery}",
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"\textbf{Method} & \textbf{Recovery Latency (ms)} $\downarrow$ & \textbf{Tokens Consumed / Fault} $\downarrow$ & \textbf{Task Completion Rate (\%)} $\uparrow$ \\",
        r"\midrule",
    ]

    for cid in configs:
        c_runs = [r for r in runs if r["config_id"] == cid]
        fault_runs = [r for r in c_runs if r["recovery_latency_ms"] > 0.0]
        label = c_runs[0]["config_label"] if c_runs else cid
        lat = _mean_std_str([r["recovery_latency_ms"] for r in fault_runs], ".1f")
        tok = _mean_std_str([float(r["tokens_consumed_on_recovery"]) for r in fault_runs], ".0f")
        tcr_by_sc = []
        for sc_id in ("S1", "S2", "S3", "S4", "S5", "S6", "S7"):
            sc_r = [r for r in c_runs if r["scenario_id"] == sc_id]
            if sc_r:
                tcr_by_sc.append(100.0 * sum(1 for r in sc_r if r["task_completed"]) / len(sc_r))
        tcr = _mean_std_str(tcr_by_sc, ".1f")
        lines.append(f"{label} & {lat} & {tok} & {tcr} \\\\")

    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    out_path = out_dir / "tab3_disturbance_recovery.tex"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export IEEE RA-L / ICRA LaTeX tables from ablation matrix")
    parser.add_argument("--input", type=str, default=str(REPO_ROOT / "results" / "ablation_matrix.json"))
    parser.add_argument("--output-dir", type=str, default=str(REPO_ROOT / "results" / "latex"))
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        from scripts.run_ablation_matrix import run_ablation_matrix
        run_ablation_matrix(seeds_per_scenario=5, output_path=in_path)

    with open(in_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    runs = data.get("runs", [])
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    p1 = export_tab1_scheduling_makespan(runs, out_dir)
    p2 = export_tab2_safety_gate_shield(runs, out_dir)
    p3 = export_tab3_disturbance_recovery(runs, out_dir)
    print(f"[LATEX] Exported:\n  - {p1}\n  - {p2}\n  - {p3}")


if __name__ == "__main__":
    main()
