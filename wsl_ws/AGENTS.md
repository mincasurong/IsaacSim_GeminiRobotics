# KNOWLEDGE BASE

## OVERVIEW
ROS 2 Jazzy workspace synced to WSL2 (`~/catkin_ws`). Core 50Hz IK controllers, Gemini VLA nodes, and verifiers.

## STRUCTURE
```
wsl_ws/
├── bringup.bash
└── src/
    └── isaac_ros2_control/
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| 50Hz IK & Bimanual Control | `src/isaac_ros2_control/isaac_ros2_control/multi_robot_controller.py` | Compiled in WSL2 |
| Gemini VLA & Guardrails | `src/isaac_ros2_control/isaac_ros2_control/gemini_robotics_node.py` | Multi-turn VLA logic |

## CONVENTIONS
- `bringup.bash` Sync Direction Warning: Syncs `wsl_ws/src` -> `~/catkin_ws/src` and strips CRLF. Keep mtimes synchronized before running `bringup.bash`.
- WSL2 Build Ignores: `franka_ros2`, `franka_description` carry `COLCON_IGNORE`.

## ANTI-PATTERNS (THIS PROJECT)
- Do not make edits in `/home/isaac/catkin_ws/src` without syncing back to Windows first, or `bringup.bash` will clobber them.
