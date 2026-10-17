# PROJECT KNOWLEDGE BASE

**Generated:** 2026-10-16T16:35:00Z
**Commit:** a479a6854d117e52573516bb84b035e44bfc6ae5
**Branch:** main

## OVERVIEW
Cross-OS Physical AI manipulation framework connecting **NVIDIA Isaac Sim 6.0** (Windows 11 host), **ROS 2 Jazzy Jalisco** (WSL2 Ubuntu 24.04), **Google Gemini Robotics-ER 2 / 3.5 Flash-Lite**, and a **React 19 + `@xyflow/react` v12 Digital Twin** over **FastDDS Unicast** (`vEthernet (WSL)`).

## MULTI-REPO TOPOLOGY (3 CONNECTED WORKSPACES)
| Workspace | Path | Role & Link Mechanism |
|-----------|------|-----------------------|
| **1. Primary Repo (Windows)** | `D:\git\IsaacSim_Gemini` (`/mnt/d/git/IsaacSim_Gemini`) | Canonical git repo: `isaacsim_scripts/`, `gemini_web_gui/`, `wsl_ws/`, `scripts/`, `tests/e2e/`. |
| **2. Isaac Sim 6.0 Build (Windows)** | `D:\git\isaacsim\src\isaacsim` | Built Kit 110 / Isaac Sim 6.0 GA (`_build\windows-x86_64\release\`). `wsl_ws` is a **directory junction** -> `D:\git\IsaacSim_Gemini\wsl_ws`. `source\standalone_examples\api\isaacsim.ros2.bridge\` mirrors `isaacsim_scripts\`. |
| **3. Live ROS 2 Workspace (WSL2)** | `\\wsl.localhost\Ubuntu-24.04\home\isaac\catkin_ws` (`/home/isaac/catkin_ws`) | Active compiled ROS 2 Jazzy workspace (`install/`, `build/`). Synced from `/mnt/d/git/IsaacSim_Gemini/wsl_ws/src/` via `bringup.bash` (`rsync -ru --delete --exclude 'libfranka*'`). |

## STRUCTURE
```
D:\git\IsaacSim_Gemini/
├── fastdds_profile.xml       # Generated FastDDS unicast locator config (Win <-> WSL2 IPs)
├── isaacsim_scripts/         # Isaac Sim 6.0 standalone scenes (run via _build/.../python.bat)
│   ├── three_robot_tower.py  # Mode 1: 3x Franka FR3 cooperative 9-block tower stacking
│   ├── conveyor_dual_robot.py# Mode 5: 2x FR3 dynamic conveyor intercept & bimanual LongBar
│   ├── assembly_dual_robot.py# Mode 6: 2x FR3 long-horizon cooperative assembly (ATAMP)
│   └── *mobile_manipulator*  # Mode 2: Nova Carter + FR3 mobile manipulator
├── gemini_web_gui/           # React 19 + @xyflow/react v12 (:5173) & Express server.cjs (:3001)
├── scripts/                  # launcher.bat, start_dashboard.bat, setup_fastdds_wsl.py
├── tests/e2e/                # 4-tier E2E test suites (feature, boundary, pairwise, scenarios)
└── wsl_ws/                   # ROS 2 source tree synced to WSL2 ~/catkin_ws
    ├── bringup.bash          # Syncs wsl_ws/src -> ~/catkin_ws/src, strips CRLF, launches ROS 2
    └── src/isaac_ros2_control# Core 50Hz IK controllers, Gemini VLA nodes, verifiers
```

## CROSS-OS BRIDGE & DATA FLOW
1. **FastDDS Unicast Discovery (`setup_fastdds_wsl.py`)**:
   - Hyper-V `vEthernet (WSL)` blocks multicast. `setup_fastdds_wsl.py` queries `wsl hostname -I` (WSL2 IP, e.g. `172.29.191.166`) and `wsl ip route` (Windows gateway IP, e.g. `172.29.176.1`), writing identical unicast `<initialPeersList>` XML profiles to `%USERPROFILE%\fastdds_profile.xml`, `D:\git\IsaacSim_Gemini\fastdds_profile.xml`, and WSL2 `~/fastdds_profile.xml`.
   - Both sides set `RMW_IMPLEMENTATION=rmw_fastrtps_cpp` and `FASTDDS_DEFAULT_PROFILES_FILE`.
2. **Windows Isaac Sim (`D:\git\isaacsim\src\isaacsim\_build\windows-x86_64\release`)**:
   - `setup_ros_env.bat` sets `ROS_DISTRO=jazzy` and mounts `exts\isaacsim.ros2.core\jazzy\lib`.
   - Scene scripts build OmniGraph (`isaacsim.ros2.bridge`) publishing `/clock`, `/tf`, `/fr3_{1..3}/joint_states`, and `/overhead_camera/{rgb,depth,camera_info}` (opt-in `--enable-cameras`), while subscribing to `/fr3_{1..3}/joint_commands`.
3. **WSL2 ROS 2 Jazzy (`/home/isaac/catkin_ws`)**:
   - `multi_robot_controller.py`: 50 Hz FSM, Damped Least Squares (DLS) IK + null-space projection (`kinematics.py`), central zone mutex (`center_occupied_by`).
   - `conveyor_dual_controller.py`: Extends `MultiRobotController` with `BimanualSynchronizedTrajectory` (`DualArmPickTrajectory`, `DualArmPlaceTrajectory`, `DualArmCircleTrajectory`) and Flying Grasp conveyor velocity matching.
   - `gemini_robotics_node.py` & `conveyor_gemini_node.py`: Multi-turn Gemini VLA function-calling orchestrator (`/gemini/custom_goal` -> `/gemini/action` -> `/gemini/action_result`) guarded by `rule_based_verifier.py`.
4. **Web Dashboard (`gemini_web_gui`)**:
   - `server.cjs` (`:3001`) spawns WSL2 `bringup.bash`, `colcon build`, `workflow_generator.py`, and `feedback_evolution_engine.py`, streaming stdout via SSE (`/api/logs`).
   - React UI (`:5173`) connects to WSL2 `rosbridge_websocket` (`ws://localhost:9090`) for Zero-Token Visual Flow DAG execution and VLA chat/telemetry.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Isaac Sim scenes & OmniGraph | `isaacsim_scripts/*.py` | Synced with `D:\git\isaacsim\src\isaacsim\source\standalone_examples\api\isaacsim.ros2.bridge\` |
| 50Hz IK & Bimanual Control | `wsl_ws/src/isaac_ros2_control/isaac_ros2_control/{multi_robot_controller,conveyor_dual_controller,kinematics}.py` | Compiled in WSL2 `/home/isaac/catkin_ws` |
| Gemini VLA & Guardrails | `wsl_ws/src/isaac_ros2_control/isaac_ros2_control/{gemini_robotics_node,gemini_tools,rule_based_verifier}.py` | Reads API key from `private/.env` |
| Visual Flow DAG & Digital Twin | `gemini_web_gui/src/{App.tsx,components/VisualWorkflowBuilder.tsx}` | Express backend in `gemini_web_gui/server.cjs` |
| FastDDS & Launchers | `scripts/{launcher.bat,setup_fastdds_wsl.py}` & `wsl_ws/bringup.bash` | Run `setup_fastdds_wsl.py` after any WSL/Windows reboot |

## CONVENTIONS & CRITICAL GOTCHAS
- **`bringup.bash` Sync Direction Warning**: `bringup.bash` runs `rsync -ru --delete` from `/mnt/d/git/IsaacSim_Gemini/wsl_ws/src/` into `/home/isaac/catkin_ws/src/` and strips `\r`. Always keep `D:\git\IsaacSim_Gemini\wsl_ws\src\` and `/home/isaac/catkin_ws/src/` synchronized before running `bringup.bash` so newer mtimes on Windows do not clobber WSL2 edits.
- **Isaac Sim Import Order**: `from isaacsim.simulation_app import SimulationApp` and `simulation_app = SimulationApp(CONFIG)` MUST execute before `import numpy`, `import omni.*`, or `from pxr import ...` so Kit mounts its internal `pip_prebundle`.
- **No In-Process `rclpy.Node` in Sim Scripts**: Never instantiate an `rclpy.Node` inside Isaac Sim Windows scripts alongside `isaacsim.ros2.bridge` (causes dual-context FastDDS access violations); use OmniGraph nodes exclusively.
- **Kill Zombie `kit.exe`**: Orphaned `kit.exe` processes publish competing `/clock` and `/tf` timestamps (`TF_OLD_DATA` freeze). Run `Stop-Process -Name "kit" -Force` before starting a new simulation.
- **Windows Batch Files**: `.bat` files must use pure 7-bit ASCII and CRLF (`\r\n`) line endings.
- **WSL2 Build Ignores**: `/home/isaac/catkin_ws/src/{franka_ros2,franka_description}` carry `COLCON_IGNORE` so `colcon build` only builds simulation packages.

## COMMANDS
```bash
# Regenerate FastDDS Unicast IPs (Windows <-> WSL2)
python D:\git\IsaacSim_Gemini\scripts\setup_fastdds_wsl.py

# Build ROS 2 package in WSL2
wsl -d Ubuntu-24.04 bash -c "cd /home/isaac/catkin_ws && source /opt/ros/jazzy/setup.bash && colcon build --symlink-install --packages-select isaac_ros2_control"

# Run WSL2 ROS 2 unit & benchmark tests
wsl -d Ubuntu-24.04 bash -c "cd /home/isaac/catkin_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash && pytest src/isaac_ros2_control/test/"
```