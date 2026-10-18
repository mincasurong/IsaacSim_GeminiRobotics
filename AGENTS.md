# PROJECT KNOWLEDGE BASE

**Generated:** 2026-10-18T00:00:00Z
**Commit:** a479a68
**Branch:** main

## OVERVIEW
Cross-OS Physical AI & Agentic Task and Motion Planning (ATAMP) framework connecting **NVIDIA Isaac Sim 6.0** (Windows 11 host), **ROS 2 Jazzy Jalisco** (WSL2 Ubuntu 24.04), **Google Gemini-4-Argon / 3.5 Flash-Lite**, and a **React 19 + `@xyflow/react` v12 Digital Twin** over **FastDDS Unicast** (`vEthernet (WSL)`).

| Workspace | Path | Role & Link Mechanism |
|-----------|------|-----------------------|
| **1. Primary Repo (Windows)** | `D:\git\IsaacSim_Gemini` (`/mnt/d/git/IsaacSim_Gemini`) | Canonical git repo: `isaacsim_scripts/`, `gemini_web_gui/`, `wsl_ws/`, `scripts/`, `tests/e2e/`, `docs/`. |
| **2. Isaac Sim 6.0 Build (Windows)** | `D:\git\isaacsim\src\isaacsim` | Built Kit 110 / Isaac Sim 6.0 GA (`_build\windows-x86_64\release\`). `wsl_ws` is a **directory junction** -> `D:\git\IsaacSim_Gemini\wsl_ws`. `source\standalone_examples\api\isaacsim.ros2.bridge\` mirrors `isaacsim_scripts\`. |
| **3. Live ROS 2 Workspace (WSL2)** | `\\wsl.localhost\Ubuntu-24.04\home\isaac\catkin_ws` (`/home/isaac/catkin_ws`) | Compiled ROS 2 Jazzy workspace (`install/`, `build/`). Synced from `/mnt/d/git/IsaacSim_Gemini/wsl_ws/src/` via `bringup.bash` (`rsync -ru --delete --exclude 'libfranka*'`). |

## STRUCTURE
```
D:\git\IsaacSim_Gemini/
├── fastdds_profile.xml       # Generated FastDDS unicast locator config (Win <-> WSL2 IPs)
├── isaacsim_scripts/         # [AGENTS.md] Isaac Sim 6.0 standalone scenes (Modes 1 & 2)
├── gemini_web_gui/           # [AGENTS.md] React 19 + @xyflow/react v12 (:5173) & Express server.cjs (:3001)
├── wsl_ws/                   # [AGENTS.md] WSL2 ROS 2 Jazzy workspace root & bringup.bash sync script
│   └── src/                  # [AGENTS.md] Colcon source boundary (franka_* carry COLCON_IGNORE)
│       └── isaac_ros2_control/isaac_ros2_control/ # [AGENTS.md] 50Hz DLS IK controller, Gemini-4-Argon VLA, verifiers
├── scripts/                  # launcher.bat, start_dashboard.bat, setup_fastdds_wsl.py
├── docs/                     # Architecture, quickstart, development & contributor guides
└── private/research/         # (Gitignored, auto-linked) Modes 5/6, ATAMP algorithms, ablation scripts & LaTeX tables
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Isaac Sim scenes & OmniGraph | `isaacsim_scripts/*.py` | Modes 1 & 2 public; Modes 5 & 6 linked from `private/research/isaacsim_scripts/` |
| 50Hz IK & Multi-Arm Control | `wsl_ws/src/isaac_ros2_control/isaac_ros2_control/{multi_robot_controller,kinematics}.py` | Compiled in WSL2 `/home/isaac/catkin_ws` |
| Gemini-4-Argon VLA & Guardrails | `wsl_ws/src/isaac_ros2_control/isaac_ros2_control/{gemini_robotics_node,gemini_tools,rule_based_verifier}.py` | Reads API key from `private/.env` |
| Visual Flow DAG & Digital Twin | `gemini_web_gui/src/{App.tsx,components/VisualWorkflowBuilder.tsx}` | Express backend in `gemini_web_gui/server.cjs` |
| FastDDS & Launchers | `scripts/{launcher.bat,start_dashboard.bat,setup_fastdds_wsl.py}` | Run `setup_fastdds_wsl.py` after any WSL/Windows reboot |
| Unit & E2E Verification | `wsl_ws/src/isaac_ros2_control/test/test_*.py` | Public IK & verifier tests; Mode 5/6 E2E & Track A-D in `private/research/tests/` |
| Private Research & Modes 5/6 | `private/research/{src,ros2_nodes,isaacsim_scripts,scripts,results,tests}/` | Auto-linked via `isaac_ros2_control/__init__.py`, `bringup.bash`, & `launcher.bat` |

## CODE MAP
| Symbol | Type | Location | Refs | Role |
|--------|------|----------|------|------|
| `forward_kinematics` | function | `wsl_ws/src/isaac_ros2_control/isaac_ros2_control/kinematics.py:203` | 19 | FR3 7-DOF end-effector pose and link transforms from DH chain |
| `RobotAction` | interface | `gemini_web_gui/src/components/theme.ts` | 16 | Structured VLA command schema across trace, DAG, and dashboard |
| `inverse_kinematics` | function | `wsl_ws/src/isaac_ros2_control/isaac_ros2_control/kinematics.py:265` | 14 | Damped Least Squares (DLS) 7-DOF IK solver with null-space projection |
| `resolve_block_name` | function | `wsl_ws/src/isaac_ros2_control/isaac_ros2_control/rule_based_verifier.py:62` | 14 | Resolves natural-language block references to scene prim names |
| `RuleBasedTaskVerifier` | class | `wsl_ws/src/isaac_ros2_control/isaac_ros2_control/rule_based_verifier.py:130` | 12 | Workspace reachability, collision zone, and bimanual promotion guardrail |
| `MultiRobotController` | class | `wsl_ws/src/isaac_ros2_control/isaac_ros2_control/multi_robot_controller.py:37` | 9 | 50 Hz 3-arm cooperative FSM controller with `center_occupied_by` mutex |
| `GeminiRoboticsNode` | class | `wsl_ws/src/isaac_ros2_control/isaac_ros2_control/gemini_robotics_node.py:79` | 7 | Multi-turn Gemini-4-Argon VLA orchestrator (`/gemini/custom_goal` -> `/gemini/action`) |
| `App` | component | `gemini_web_gui/src/App.tsx` | 6 | Top-level Digital Twin UI managing `roslib` (`:9090`) and SSE logs (`:3001`) |

## CONVENTIONS
- **FastDDS Unicast Bridge (`setup_fastdds_wsl.py`)**: Hyper-V `vEthernet (WSL)` blocks multicast. `setup_fastdds_wsl.py` writes identical unicast `<initialPeersList>` XML profiles (WSL2 IP + Windows gateway IP) to `%USERPROFILE%\fastdds_profile.xml`, `D:\git\IsaacSim_Gemini\fastdds_profile.xml`, and WSL2 `~/fastdds_profile.xml` with `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`.
- **`bringup.bash` Sync Direction**: `wsl_ws/bringup.bash` runs `rsync -ru --delete --exclude 'libfranka*'` from `/mnt/d/git/IsaacSim_Gemini/wsl_ws/src/` into `/home/isaac/catkin_ws/src/` and strips `\r`. Keep Windows `wsl_ws/src/` and WSL2 `~/catkin_ws/src/` synchronized before running `bringup.bash` so newer Windows mtimes do not overwrite WSL2 edits.
- **Cross-Subtree Python Path Injection**: `src/shield/`, `scripts/run_ablation_matrix.py`, and `tests/e2e/` dynamically prepend `wsl_ws/src/isaac_ros2_control/isaac_ros2_control` to `sys.path` to run pure-Python kinematics and verifiers without a live ROS 2 runtime.
- **Windows Batch Files**: `.bat` scripts in `scripts/` must use pure 7-bit ASCII and CRLF (`\r\n`) line endings.

## ANTI-PATTERNS (THIS PROJECT)
- **Never instantiate `rclpy.Node` inside Isaac Sim Windows scripts**: Dual FastDDS contexts alongside `isaacsim.ros2.bridge` trigger native access violations; use OmniGraph nodes exclusively.
- **Never import `numpy`, `omni.*`, or `pxr` before `SimulationApp(CONFIG)`**: Kit must initialize first to mount its internal `pip_prebundle`.
- **Never skip `tinyxml2.dll` pre-load in Sim scripts**: `exts\isaacsim.ros2.core\jazzy\lib\tinyxml2.dll` (92 KB) must be pre-loaded via `ctypes.WinDLL` before `SimulationApp` so `omni.kit.asset_converter` does not load its incompatible 104 KB DLL (`fastrtps-2.14.dll` crash).
- **Never leave zombie `kit.exe` processes running**: Competing `/clock` and `/tf` publishers cause `TF_OLD_DATA` freezes; run `Stop-Process -Name "kit" -Force` before launching a new scene.
- **Never spawn `bringup.bash` non-interactively without a `<mode>` argument**: Omitting `<mode>` (`1`..`5` or `7`/`8`) hangs on interactive `read -p`.

## UNIQUE STYLES
- **ATAMP Closed-Loop Pipeline (`src/` + `docs/architecture_hooks.json`)**: `Plan (DAG) -> Pre-Flight Gate (Shield) -> Contention-Aware Wavefront Schedule (RCPSP) -> Execute (ROS 2 50Hz) -> Write-Back / 0-Token Subgraph Recovery`.
- **Dual-Bridge Web Orchestration (`gemini_web_gui`)**: Express (`server.cjs` on `:3001`) spawns WSL2 `bringup.bash`/`colcon build` and streams stdout via SSE (`/api/logs`), while React (`:5173`) talks directly to WSL2 `rosbridge_websocket` (`ws://localhost:9090`) for Zero-Token Visual Flow DAG execution.
- **50 Hz DLS IK + Central Zone Mutex**: `MultiRobotController` and `ConveyorDualController` run 50 Hz Damped Least Squares IK with null-space posture projection, `center_occupied_by` mutex arbitration, and quintic smoothstep bimanual trajectories.

## COMMANDS
```bash
# Regenerate FastDDS Unicast IPs (Windows <-> WSL2)
python D:\git\IsaacSim_Gemini\scripts\setup_fastdds_wsl.py

# Build ROS 2 package in WSL2
wsl -d Ubuntu-24.04 bash -c "cd /home/isaac/catkin_ws && source /opt/ros/jazzy/setup.bash && colcon build --symlink-install --packages-select isaac_ros2_control"

# Run WSL2 ROS 2 unit tests & standalone Windows E2E suites
wsl -d Ubuntu-24.04 bash -c "cd /home/isaac/catkin_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash && pytest src/isaac_ros2_control/test/"
pytest tests/e2e/
```

## NOTES
- **WSL2 Build Ignores**: `/home/isaac/catkin_ws/src/{franka_ros2,franka_description}` carry `COLCON_IGNORE` so `colcon build` only compiles active simulation packages.
- **Simulation Clock Requirement**: All WSL2 nodes require `use_sim_time: True` synced to Isaac Sim `/clock`; if arms do not move, verify `/clock` is publishing and FastDDS IPs match `wsl hostname -I`.