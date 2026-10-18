# WSL_WS KNOWLEDGE BASE

## OVERVIEW
WSL2 ROS 2 Jazzy workspace orchestration root, environment provisioning scripts, and MCP server (Score: 11 — distinct cross-OS workspace boundary).

## STRUCTURE
```
wsl_ws/
├── bringup.bash          # Interactive/CLI launcher: rsyncs src/, configures FastDDS, starts launch targets
├── setup_all.sh          # One-shot WSL2 Ubuntu 24.04 + ROS 2 Jazzy + MoveIt 2 provisioning entry point
├── scripts/              # Modular setup scripts (setup_*.sh, verify_setup.sh) and ros2_mcp.py stdio server
├── docs/                 # Multi-robot ROS 2 workflow architecture notes (multi_robot_workflow.md)
├── src/                  # Colcon package sources (isaac_ros2_control, multi_robot_*, franka_*)
└── build/ install/ log/  # Local colcon build artifacts (canonical runtime lives in ~/catkin_ws)
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Interactive / CLI ROS 2 Bringup | `bringup.bash` | Supports modes `1`..`5` or custom `<pkg> <launch_file>` args |
| Full WSL2 Provisioning | `setup_all.sh`, `scripts/setup_*.sh` | Installs ROS 2 Jazzy, colcon, MoveIt 2, NVIDIA container toolkit |
| Environment Verification | `scripts/verify_setup.sh` | Checks ROS 2 Jazzy env, FastDDS profile, and topic visibility |
| ROS 2 MCP Server (JSON-RPC) | `scripts/ros2_mcp.py` | Exposes `get_node_graph`, `check_isaac_sim_status`, `echo_topic`, `send_vla_goal` |
| Architecture Reference | `docs/ISAAC_SIM_WINDOWS_SETUP.md` | Cross-OS FastDDS & Isaac Sim Windows setup reference |

## CONVENTIONS
- **Non-Interactive Bringup Invocation**: Pass `<mode>` (`1`=rule-based, `2`=single-arm, `3`=MoveIt, `4`=Gemini VLA, `5`=conveyor dual-arm) or `<pkg> <launch_file>` directly to `bringup.bash` when spawning from `server.cjs` or automated scripts.
- **Line Endings in `wsl_ws/`**: All `.sh` and `.bash` files under `wsl_ws/` must use LF (`\n`) endings; `bringup.bash` runs `sed -i 's/\r$//'` across `~/catkin_ws/src` after every `rsync`.
- **FastDDS Profile Resolution**: `bringup.bash` exports `RMW_IMPLEMENTATION=rmw_fastrtps_cpp` and loads `~/fastdds_profile.xml` only if present on the WSL2 filesystem.
- **ROS Log Directory Pre-Creation**: `bringup.bash` creates `~/.ros/log` before sourcing setup files to prevent ROS 2 Jazzy symlink warnings.

## ANTI-PATTERNS
- **NEVER** run `colcon build` against `/mnt/d/git/IsaacSim_Gemini/wsl_ws` on Windows/DrvFs for production runs; always compile inside native ext4 `/home/isaac/catkin_ws` in WSL2 to avoid 9P filesystem bottlenecks and symlink errors.
- **DO NOT** invoke `bringup.bash` without arguments from headless subprocesses (`server.cjs` / CI), or `read -p` will block indefinitely waiting for stdin.
- **NEVER** hardcode ephemeral WSL2 or Windows Hyper-V IP addresses inside `scripts/setup_ros2_bridge_config.sh` or `.bashrc`; rely on generated `~/fastdds_profile.xml`.
- **DO NOT** run `ros2_mcp.py` without sourcing `/opt/ros/jazzy/setup.bash` and `~/catkin_ws/install/setup.bash`, or custom service/topic introspection calls will fail.
