#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

for _cand in (
    Path(__file__).resolve().parents[2] / "wsl_ws" / "src" / "isaac_ros2_control" / "isaac_ros2_control",
    Path(__file__).resolve().parents[1] / "src" / "isaac_ros2_control" / "isaac_ros2_control",
    Path.home() / "catkin_ws" / "src" / "isaac_ros2_control" / "isaac_ros2_control",
    Path.home() / "mujoco_ws",
):
    if _cand.is_dir() and str(_cand) not in sys.path:
        sys.path.insert(0, str(_cand))

def run_efe_exam_evaluation() -> Dict[str, Any]:
    return {"status": "private_research_module_not_loaded", "passed_tasks": 0, "total_tasks": 0}

try:
    from isaac_ros2_control.mujoco_env import (  # noqa: E402
        RobomimicDatasetRecorder,
        StampMuJoCoEnv,
        export_libero_bddl_task,
        generate_mjcf_xml,
        run_headless_closed_loop_mode1,
        run_headless_closed_loop_mode2,
        run_headless_closed_loop_mode3,
    )
except ImportError:
    from mujoco_env import (  # noqa: E402
        RobomimicDatasetRecorder,
        StampMuJoCoEnv,
        export_libero_bddl_task,
        generate_mjcf_xml,
        run_headless_closed_loop_mode1,
        run_headless_closed_loop_mode2,
        run_headless_closed_loop_mode3,
    )

try:
    import kinematics
except ImportError:
    from isaac_ros2_control import kinematics


MODE_NAMES = {
    1: "mode1_tower_3arm",
    2: "mode2_conveyor_dual",
    3: "mode3_efe_sdl_deformable",
}


def export_workspace_artifacts(ws_root: Path) -> Dict[str, Any]:
    mjcf_dir = ws_root / "mjcf"
    bddl_dir = ws_root / "bddl"
    datasets_dir = ws_root / "datasets"
    mjcf_dir.mkdir(parents=True, exist_ok=True)
    bddl_dir.mkdir(parents=True, exist_ok=True)
    datasets_dir.mkdir(parents=True, exist_ok=True)

    exported_mjcf: List[str] = []
    exported_bddl: List[str] = []
    for mode_id, mname in MODE_NAMES.items():
        xml_path = mjcf_dir / f"{mname}.xml"
        xml_path.write_text(generate_mjcf_xml(mode_id), encoding="utf-8")
        exported_mjcf.append(str(xml_path))

        bddl_path = bddl_dir / f"{mname}.bddl"
        bddl_path.write_text(export_libero_bddl_task(mode=mode_id, task_name=mname), encoding="utf-8")
        exported_bddl.append(str(bddl_path))

    env = StampMuJoCoEnv(mode=3, render_obs=False)
    rec = RobomimicDatasetRecorder(env_name="STAMP_Mode3_EFE_WSL2", mode=3)
    obs = env.reset()
    for step_idx in range(10):
        act = {arm: list(kinematics.FR3_HOME_CONFIG) + [0.04] for arm in env.bases}
        next_obs = env.step(act)
        rec.record_step(obs, act, reward=float(step_idx == 9), done=(step_idx == 9))
        obs = next_obs
    ds_summary = rec.save(datasets_dir / "mode3_efe_robomimic_demo.json")

    return {
        "workspace_root": str(ws_root),
        "mjcf_files": exported_mjcf,
        "bddl_files": exported_bddl,
        "sample_dataset": ds_summary,
    }


def run_self_test(mode: int) -> Dict[str, Any]:
    env = StampMuJoCoEnv(mode=mode, render_obs=True, camera_width=96, camera_height=72)
    obs0 = env.reset()
    for _ in range(20):
        act = {arm: list(kinematics.FR3_HOME_CONFIG) + [0.04] for arm in env.bases}
        obs = env.step(act)
    if mode == 1:
        closed_loop = run_headless_closed_loop_mode1(num_blocks=9)
    elif mode == 2:
        closed_loop = run_headless_closed_loop_mode2()
    else:
        closed_loop = run_headless_closed_loop_mode3()
    return {
        "mode": mode,
        "mode_name": MODE_NAMES.get(mode, f"mode_{mode}"),
        "fr3_stl_meshes_loaded": int(env.model.nmesh),
        "sim_time_sec": obs["sim_time_sec"],
        "robots": list(obs["robots"].keys()),
        "num_objects": len(obs["objects"]),
        "objects": list(obs["objects"].keys()),
        "agentview_shape": list(obs["agentview_image"].shape),
        "wrist_cam_shape": list(obs["robot0_eye_in_hand_image"].shape),
        "headless_closed_loop_multi_task": closed_loop,
    }


def run_ros2_or_standalone_loop(mode: int, enable_viewer: bool, max_steps: int = 0) -> int:
    try:
        import rclpy
        from isaac_ros2_control.mujoco_sim_node import MuJoCoWorkcellNode

        rclpy.init()
        node = MuJoCoWorkcellNode(workcell_mode=mode, enable_viewer=enable_viewer and bool(os.environ.get("DISPLAY")))

        step_count = 0
        try:
            while rclpy.ok():
                rclpy.spin_once(node, timeout_sec=0.02)
                step_count += 1
                if max_steps > 0 and step_count >= max_steps:
                    break
                if node._viewer is not None and not node._viewer.is_running():
                    break
        except KeyboardInterrupt:
            pass
        finally:
            if node._viewer is not None:
                try:
                    node._viewer.close()
                except Exception:
                    pass
            node.destroy_node()
            rclpy.shutdown()
        return 0
    except ImportError:
        env = StampMuJoCoEnv(mode=mode, render_obs=False)
        env.reset()
        viewer = None
        if enable_viewer and os.environ.get("DISPLAY"):
            try:
                import mujoco.viewer

                viewer = mujoco.viewer.launch_passive(env.model, env.data)
            except Exception:
                viewer = None
        steps = max_steps if max_steps > 0 else 250
        for _ in range(steps):
            env.step({})
            if viewer is not None and viewer.is_running():
                viewer.sync()
            time.sleep(0.01)
        if viewer is not None:
            viewer.close()
        return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="WSL2 Native MuJoCo + LIBERO/robomimic Scene Runner")
    parser.add_argument("--mode", type=int, choices=[1, 2, 3], default=3, help="Workcell mode (1, 2, or 3).")
    parser.add_argument("--viewer", action="store_true", help="Open WSLg 3D interactive MuJoCo viewer.")
    parser.add_argument("--export-ws", default="", help="Provision MJCF, BDDL, and robomimic files into directory.")
    parser.add_argument("--test", action="store_true", help="Run fast self-test and exit.")
    parser.add_argument("--efe-eval", action="store_true", help="Run Embodied First Exam Mode 3 evaluation.")
    parser.add_argument("--max-steps", type=int, default=0, help="Stop after N steps (0 = run until interrupted).")
    args = parser.parse_args(argv)

    if args.export_ws:
        res = export_workspace_artifacts(Path(args.export_ws))
        print(json.dumps(res, indent=2))
        return 0

    if args.efe_eval:
        res = run_efe_exam_evaluation()
        print(json.dumps(res, indent=2))
        return 0

    if args.test:
        res = run_self_test(args.mode)
        print(json.dumps(res, indent=2))
        return 0

    return run_ros2_or_standalone_loop(args.mode, enable_viewer=args.viewer, max_steps=args.max_steps)


if __name__ == "__main__":
    raise SystemExit(main())
