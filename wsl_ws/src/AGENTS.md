# WSL_WS/SRC KNOWLEDGE BASE

## OVERVIEW
Colcon multi-package source tree combining `isaac_ros2_control` (ament_python), multi-FR3 URDF/MoveIt 2 configs, and vendored Franka packages (Score: 10 — colcon package boundary).

## STRUCTURE
```
wsl_ws/src/
├── isaac_ros2_control/          # Active ament_python package: setup.py, launch/, scripts/, test/, isaac_ros2_control/
├── multi_robot_description/     # Multi-FR3 URDF/XACRO descriptions (urdf/three_robot.urdf.xacro, launch/view_scene.launch.py)
├── multi_robot_moveit_config/   # MoveIt 2 SRDF/joint-limit generators (generate_srdf.py, generate_limits.py, config/)
├── franka_description/          # Vendored Franka Emika robot URDFs & meshes (COLCON_IGNORE in WSL2)
└── franka_ros2/                 # Vendored physical Franka C++ hardware drivers (COLCON_IGNORE in WSL2)
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Package Manifest & Console Entrypoints | `isaac_ros2_control/setup.py`, `isaac_ros2_control/package.xml` | Registers 10 console scripts and installs `launch/`, `resource/`, `scripts/` |
| Executable Node Wrappers | `isaac_ros2_control/scripts/*` | 8 executable shims installed into `install/isaac_ros2_control/lib/isaac_ros2_control/` |
| ROS 2 Launch Topologies | `isaac_ros2_control/launch/*.launch.py` | `gemini_controller`, `multi_robot_rule_based`, `conveyor_dual_controller`, `moveit_controller` |
| Unit & Verification Suites | `isaac_ros2_control/test/test_*.py` | Pytest suites for IK, verifier guardrails, and bimanual trajectories |
| Multi-FR3 Scene URDF / XACRO | `multi_robot_description/urdf/three_robot.urdf.xacro` | Defines 3-arm Franka FR3 transforms (`robot{1..3}_fr3_*`) and `view_scene.launch.py` |
| MoveIt 2 SRDF & Limit Generators | `multi_robot_moveit_config/generate_srdf.py`, `generate_limits.py` | Generates `three_robot_scene` SRDF groups (`fr3_{1..3}_arm`) and `joint_limits.yaml` |
| MoveIt 2 Planning Pipeline | `multi_robot_moveit_config/launch/move_group.launch.py` | Launches OMPL / kinematics config from `multi_robot_moveit_config/config/*.yaml` |

## CONVENTIONS
- **Dual Entrypoint Registration (`setup.py` + `scripts/`)**: Every ROS 2 node executable in `isaac_ros2_control` is declared in `setup.py` `entry_points['console_scripts']` AND mirrored by a wrapper in `isaac_ros2_control/scripts/` for `ros2 launch` lookup under `lib/isaac_ros2_control`.
- **Launch-File Sim Time Injection**: Pass `parameters=[{'use_sim_time': True}]` inside `launch/*.launch.py` `Node(...)` declarations rather than re-declaring `use_sim_time` inside Python node classes.
- **Generated MoveIt Configs**: Edit `multi_robot_moveit_config/generate_srdf.py` or `generate_limits.py` when changing `robot{1..3}_fr3_` link/joint prefixes instead of hand-editing `config/three_robot.srdf`.
- **Selective Colcon Compilation**: Build with `--packages-select isaac_ros2_control` (or `multi_robot_description multi_robot_moveit_config`); `franka_ros2` and `franka_description` are hardware/mesh reference trees skipped in simulation builds.

## ANTI-PATTERNS
- **NEVER** add a new ROS 2 node in `isaac_ros2_control/isaac_ros2_control/` without registering it in `isaac_ros2_control/setup.py` (`console_scripts` and `data_files` if launched via `Node(executable=...)`).
- **DO NOT** modify C++ hardware controllers inside `franka_ros2/` expecting changes in Isaac Sim; simulation joint commands flow directly through `isaac_ros2_control` Python nodes over `/fr3_{1..3}/joint_commands`.
- **NEVER** break the `robot{1..3}_fr3_` joint/link naming contract between `multi_robot_description/urdf/` and `multi_robot_moveit_config/config/`, or MoveIt 2 planning groups will fail to bind.
- **DO NOT** place slow network/LLM calls inside `isaac_ros2_control/test/test_*.py`; unit tests must run offline and deterministically under `pytest`.
