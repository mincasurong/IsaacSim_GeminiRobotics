# OVERVIEW
ROS 2 Jazzy workspace source (`wsl_ws/src`), mirrored to `\\wsl.localhost\Ubuntu-24.04\home\isaac\catkin_ws\src` and linked from `D:\git\isaacsim\src\isaacsim\wsl_ws`.

## STRUCTURE
```
wsl_ws/src/
├── isaac_ros2_control/          # Active Python package: 50Hz IK controllers, Gemini VLA nodes, verifiers
│   ├── isaac_ros2_control/      # Core modules (multi_robot_controller, conveyor_dual_controller, gemini_robotics_node, kinematics, etc.)
│   ├── launch/                  # Launch files (gemini_controller, multi_robot_rule_based, conveyor_dual_controller, moveit_controller)
│   └── test/                    # Unit & benchmark tests (in WSL2 ~/catkin_ws/src/isaac_ros2_control/test)
├── multi_robot_description/     # Multi-FR3 URDFs and RViz configs
├── multi_robot_moveit_config/   # MoveIt 2 SRDF, kinematics, and joint limit generators
├── franka_description/          # Franka Emika robot URDFs/meshes (COLCON_IGNORE in WSL2)
└── franka_ros2/                 # Physical Franka hardware drivers (COLCON_IGNORE in WSL2)
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| 3-Arm Tower FSM & Mutex | `isaac_ros2_control/multi_robot_controller.py` | 50Hz loop, `/fr3_{1..3}/joint_commands`, `center_occupied_by` lock |
| Dual-Arm & Conveyor Control | `isaac_ros2_control/conveyor_dual_controller.py` | `BimanualSynchronizedTrajectory`, Flying Grasp velocity matching |
| Analytical & Numerical IK | `isaac_ros2_control/kinematics.py` | FR3 7-DOF DLS IK + null-space projection & Yoshikawa manipulability |
| Gemini VLA Orchestration | `isaac_ros2_control/gemini_robotics_node.py` | 4-turn multi-agent CoT, function calling, `/gemini/action` |
| Safety Verifier | `isaac_ros2_control/rule_based_verifier.py` | Pre-execution reachability, collision zone, and dual-arm promotion guardrails |
| DAG Workflow Generator | `isaac_ros2_control/workflow_generator.py` | Generates `@xyflow/react` parallel DAG JSON from natural language |

## CONVENTIONS & GOTCHAS
- **Sync Hazard (`bringup.bash`)**: `bringup.bash` runs `rsync -ru --delete` from Windows `wsl_ws/src/` to WSL2 `~/catkin_ws/src/` and strips `\r` line endings. Note that `~/catkin_ws/src/isaac_ros2_control` currently contains newer Oct 11-12 bimanual/conveyor fixes and unit tests (`test/*.py`) whose mtimes (`2026-10-11`) are older than Windows git checkout timestamps (`2026-10-13`). Sync `~/catkin_ws/src/isaac_ros2_control` back to Windows before running `bringup.bash`.
- **Simulation Time**: Always pass `'use_sim_time': True` via launch file parameters (never call `self.declare_parameter('use_sim_time')` in ROS 2 Jazzy nodes) and initialize `tf2_ros.Buffer(node=self)`.
- **`verify_tower` Read-Only Rule**: `verify_tower` in `multi_robot_controller.py` must remain strictly read-only and never call `_send_home_cmd()` (which opens grippers and drops held blocks).