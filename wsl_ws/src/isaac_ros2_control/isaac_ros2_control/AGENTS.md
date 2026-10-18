# ISAAC_ROS2_CONTROL PYTHON MODULE KNOWLEDGE BASE

## OVERVIEW
Core Python control, numerical IK, and Gemini-4-Argon VLA orchestration module (`16` public modules + `private/research/ros2_nodes` auto-linked via `__init__.py`; Score: 16 — high complexity & symbol centrality).

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| 3-Arm 50 Hz FSM & Central Mutex | `multi_robot_controller.py` | `MultiRobotController` (979 LOC): pick/place FSM, `center_occupied_by` lock, `/fr3_{1..3}/joint_commands` |
| 7-DOF DLS IK & Null-Space Math | `kinematics.py` | `forward_kinematics`, `inverse_kinematics`, `manipulability`, `compute_symmetric_grasp_quat` |
| Multi-Turn Gemini VLA Node | `gemini_robotics_node.py` | `GeminiRoboticsNode` (1,058 LOC): CoT loop, tool dispatch, `/gemini/action` & `/gemini/action_result` |
| VLA Prompts, Tools & Config | `gemini_prompts.py`, `gemini_tools.py`, `gemini_config.py`, `gemini_utils.py` | System prompts, function declarations, `private/.env` loader (`load_env`), image encoding |
| Pre-Execution Safety Guardrails | `rule_based_verifier.py` | `RuleBasedTaskVerifier`, `resolve_block_name`, `normalize_robot_id`, `RuleBasedTaskGenerator` link |
| Visual Flow DAG Generator | `workflow_generator.py` | NL-to-`@xyflow/react` parallel DAG generation (`gemini-3.5-flash-lite` + deterministic fallback) |
| Telemetry & Vision Nodes | `monitoring_agent_node.py`, `vision_tracker_node.py` | `HealthAuditor` (`/gemini/monitoring_summary`), RGB/depth back-projection |
| Workspace Geometry & MoveIt | `workspace_config.py`, `workspace_state.py`, `trajectory_adapter.py`, `multi_robot_moveit_controller.py` | Robot base frames, block registries, MoveIt 2 trajectory adaptation |
| Private Research Nodes (Linked) | `../../../../private/research/ros2_nodes/*.py` | `conveyor_dual_controller`, `conveyor_gemini_node`, `rule_based_task_generator`, `skill_library`, `feedback_evolution_engine`, `experiment_*` |

## CONVENTIONS
- **Coordinate Frame Transforms**: Convert world targets into each robot's local `fr3_link0` frame via `world_to_local_base(pos_w, robot_id)` before calling `inverse_kinematics()`, as DLS IK operates in the arm base frame.
- **Quintic Smoothstep Trajectories**: Bimanual synchronized motion in `conveyor_dual_controller.py` interpolates Cartesian waypoints with `quintic_smoothstep(t)` so both arms share zero endpoint velocity/acceleration spikes.
- **Normalized Vision Coordinates**: Vision grounding helpers in `gemini_prompts.py` and `vision_tracker_node.py` expect normalized `[y, x]` coordinates in `[0, 1000]` before camera intrinsics back-projection.
- **Action Verification Gate**: Route every VLA tool call (`pick_and_place`, `dual_arm_pick_and_place`, `intercept_moving_object`) through `RuleBasedTaskVerifier` prior to dispatching `/gemini/action`.
- **Canonical Robot & Block Normalization**: Normalize free-form LLM identifiers via `normalize_robot_id()` (`fr3_1`..`fr3_3`) and `resolve_block_name()` before indexing controller state dictionaries.
- **UTF-8 BOM Handling**: `workspace_state.py` starts with a UTF-8 BOM (`U+FEFF`); use `encoding='utf-8-sig'` when parsing module ASTs or reading source files programmatically.

## ANTI-PATTERNS
- **NEVER** call `_send_home_cmd()` inside `verify_tower` (`multi_robot_controller.py`); verification passes must stay strictly read-only so active grippers do not open and drop held blocks.
- **DO NOT** dispatch concurrent pick/place actions to the same `robot_id` within a single Gemini VLA turn; wait for `/gemini/action_result` completion before issuing the next command to that arm.
- **NEVER** bypass `center_occupied_by` mutex checks when transitioning an arm into the shared central tower zone (`[0.5, 0.0, z]`), or arms will collide mid-transfer.
- **DO NOT** return markdown code fences or prose when requesting raw `[y, x]` bounding-box/point coordinates in `gemini_prompts.py`.
- **NEVER** block the 50 Hz timer callback in `multi_robot_controller.py` or `conveyor_dual_controller.py` with synchronous Gemini API requests; keep LLM calls isolated inside `gemini_robotics_node.py` / `conveyor_gemini_node.py`.
- **DO NOT** hardcode `GEMINI_API_KEY` in node files; load credentials exclusively through `gemini_config.load_env()` (`private/.env` or environment variables).
