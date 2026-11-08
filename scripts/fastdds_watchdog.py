from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[1]


class FastDDSBridgeWatchdog:
    def __init__(
        self,
        wsl_distro: str = "Ubuntu-24.04",
        bringup_mode: int = 1,
        timeout_sec: float = 8.0,
        log_path: Optional[Path] = None,
    ) -> None:
        self.wsl_distro = wsl_distro
        self.bringup_mode = int(bringup_mode)
        self.timeout_sec = float(timeout_sec)
        self.log_path = log_path or (_REPO_ROOT / "logs" / "watchdog_events.jsonl")
        self.restart_count = 0

    def check_clock_heartbeat(self, dry_run: bool = False) -> Dict[str, Any]:
        if dry_run:
            return {"healthy": True, "clock_active": True, "mode": "dry_run"}

        cmd = [
            "wsl",
            "-d",
            self.wsl_distro,
            "bash",
            "-c",
            "source /opt/ros/jazzy/setup.bash && timeout 3 ros2 topic list",
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
                check=False,
            )
            topics = proc.stdout.splitlines() if proc.stdout else []
            has_clock = "/clock" in topics or "/tf" in topics
            return {
                "healthy": proc.returncode == 0 and has_clock,
                "clock_active": has_clock,
                "returncode": proc.returncode,
                "topics_detected": len(topics),
            }
        except Exception as exc:
            return {"healthy": False, "clock_active": False, "error": str(exc)}

    def refresh_fastdds_and_restart_bridge(self, dry_run: bool = False) -> Dict[str, Any]:
        self.restart_count += 1
        setup_script = _REPO_ROOT / "scripts" / "setup_fastdds_wsl.py"
        actions_taken = ["refresh_fastdds_profile", "restart_wsl_ros2_bridge"]

        if not dry_run:
            if setup_script.exists():
                subprocess.run(
                    [sys.executable, str(setup_script)],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
            restart_cmd = (
                "pkill -9 -f '_ros2_daemon|rosbridge|gemini_controller|multi_robot' 2>/dev/null || true; "
                f"cd ~/catkin_ws && bash bringup.bash {self.bringup_mode} >/tmp/stamp_bringup.log 2>&1 &"
            )
            subprocess.run(
                ["wsl", "-d", self.wsl_distro, "bash", "-c", restart_cmd],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )

        event = {
            "timestamp_iso": datetime.now(timezone.utc).isoformat(),
            "event": "FASTDDS_BRIDGE_RESTART",
            "restart_count": self.restart_count,
            "bringup_mode": self.bringup_mode,
            "actions": actions_taken,
            "dry_run": dry_run,
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
        return event

    def run_once(self, dry_run: bool = False, force_hang: bool = False) -> Dict[str, Any]:
        status = self.check_clock_heartbeat(dry_run=dry_run)
        if force_hang:
            status["healthy"] = False
            status["clock_active"] = False
        if not status.get("healthy", False):
            recovery = self.refresh_fastdds_and_restart_bridge(dry_run=dry_run)
            return {"status": status, "restarted": True, "recovery": recovery}
        return {"status": status, "restarted": False}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="WSL2 <-> Windows Isaac Sim FastDDS Watchdog")
    parser.add_argument("--mode", type=int, default=1, help="bringup.bash mode to relaunch on hang.")
    parser.add_argument("--dry-run", action="store_true", help="Run without spawning WSL subprocesses.")
    parser.add_argument("--simulate-hang", action="store_true", help="Simulate a bridge hang to verify recovery.")
    parser.add_argument("--Watch-cycles", type=int, default=1, help="Number of check cycles to execute.")
    parser.add_argument("--interval-sec", type=float, default=5.0, help="Seconds between cycles.")
    args = parser.parse_args(argv)

    watchdog = FastDDSBridgeWatchdog(bringup_mode=args.mode)
    last_result: Dict[str, Any] = {}
    for cycle in range(args.Watch_cycles):
        last_result = watchdog.run_once(dry_run=args.dry_run, force_hang=args.simulate_hang)
        if cycle + 1 < args.Watch_cycles:
            time.sleep(args.interval_sec)
    print(json.dumps(last_result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
