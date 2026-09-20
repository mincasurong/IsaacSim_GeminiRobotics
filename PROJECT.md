# Project: Isaac Sim Kitchen Manipulation & Multi-Robot Collaboration

## Architecture
- **Simulation Layer**: Standalone Omniverse Isaac Sim simulation script (`isaacsim_scripts/kitchen_three_robot.py`) hosting 3x Franka FR3 arms on a kitchen counter, procedural rigid bodies (dishes, cups, oversized long bar), synthetic overhead RGB-D camera via OmniGraph Replicator, and dynamic `/tf` transform tree broadcaster. Preserves existing `three_robot_tower.py`.
- **Control & Kinematics Layer**: ROS 2 Python node (`multi_robot_controller.py`) in `isaac_ros2_control` package operating at 50 Hz. Features MoveIt-style quintic polynomial trajectory generation, DLS numerical IK with null-space biasing (`kinematics.py`), single-arm kitchenware affordances (`KITCHEN_AFFORDANCES`), and closed-chain synchronized dual-arm virtual rigid-body trajectory generation maintaining constant grasp separation.
- **Cognitive VLA Layer**: ROS 2 Python node (`gemini_robotics_node.py`) interfacing with Google Gemini 2.0 / 3.7 models. Incorporates 4-turn multi-agent brainstorming (🦾 Orchestrator, 📐 Spatial Architect, ⚡ Agility Optimizer), tool definitions (`gemini_tools.py`), affordance classification (single-arm vs dual-arm), and prompt templates (`gemini_prompts.py`).
- **Digital Twin & Visualization Layer**: React 19 + `@xyflow/react` + Tailwind CSS + Vite web application (`gemini_web_gui/`). Connects to ROS 2 via `rosbridge_websocket` (`ws://localhost:9090`), rendering 2D SceneMap with kitchen object tokens, dynamic collaborative dual-arm linkage in the workflow graph, and kitchen quick-prompt chips.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Standalone Kitchen Sim Script | Dedicated `isaacsim_scripts/kitchen_three_robot.py` with kitchen table, 3 FR3 arms, preserving `three_robot_tower.py` | M1 | R1, AC-1, AC-2 |
| 2 | Procedural Flat Dishes | Procedural shallow plates/dishes with realistic physics colliders, mass (0.18kg), friction, and textures | M1 | R1, AC-1 |
| 3 | Procedural Cylindrical Cups | Procedural cups/mugs with cylinder colliders, mass (0.15kg), friction, and textures | M1 | R1, AC-1 |
| 4 | Procedural Oversized Long Bar | Rigid-body bar spanning reach of two adjacent robots (~0.44-0.55m) with realistic colliders | M1 | R1, AC-1 |
| 5 | Synthetic Overhead RGB-D Camera | Overhead camera publishing `/overhead_camera/rgb`, `/overhead_camera/depth`, and camera info | M1 | R1, AC-1 |
| 6 | Dynamic /tf Tree Broadcasting | OmniGraph ActionGraph publishing dynamic transforms for all kitchen objects and robot frames | M1 | R1, AC-3 |
| 7 | Single-Arm Dish Manipulation | Grasp height, rim-pinch offset, and approach tailored for shallow plates with touch sensor verification | M2 | R2, AC-4 |
| 8 | Single-Arm Cup Manipulation | Mid-height body clamping, cylindrical grasp offset, and touch sensor verification | M2 | R2, AC-4 |
| 9 | Kitchen Table Clearing/Organizing | Primitive action sequence for clearing and repositioning kitchenware across workspaces | M2 | R2, AC-4 |
| 10 | Dual-Arm Kinematic Coordination | Closed-chain kinematic coordination maintaining rigid-body distance invariance between two FR3 arms | M3 | R3, AC-5 |
| 11 | Synchronized Approach & Contact Closure | Lock-step state machine for simultaneous approach and contact grasp closure on opposite ends of the bar | M3 | R3, AC-5 |
| 12 | Coupled Cartesian Transport | Coupled trajectory generation moving the long bar smoothly without joint limit violation or drop | M3 | R3, AC-5 |
| 13 | Synchronized Release & Compliance | Lock-step gripper release and retreat with outward elbow collision avoidance | M3 | R3, AC-5 |
| 14 | Collaborative Telemetry Publishing | Publishing active dual-arm collaborative state and telemetry on `/multi_robot/robot_metrics` | M3 | R3, AC-5, AC-8 |
| 15 | Fix Utility Function Bug | Implement missing `resolve_object_key` in `gemini_utils.py` for relative placement | M4 | R4, AC-6, AC-7 |
| 16 | Affordance Reasoning Rules | Cognitive prompt rules classifying single-arm (dishes, cups) vs dual-arm (oversized long bar) | M4 | R4, AC-6 |
| 17 | Dual-Arm Action Tool Schemas | Extended tool declarations (`dual_arm_transport`) in `gemini_tools.py` for multi-robot dispatch | M4 | R4, AC-7 |
| 18 | Kitchen Multi-Agent Prompts | Spatial Architect (📐) and Agility Optimizer (⚡) prompts for kitchen layout and dual-arm concurrency | M4 | R4, AC-6 |
| 19 | SceneMap Kitchen Object Tokens | 2D SVG tokens for dishes, cups, and long bar in `SceneMap.tsx` | M5 | R5, AC-8 |
| 20 | Dual-Arm Linkage Visualization | Dynamic collaborative linkage edge in React Flow (`AgentWorkflowGraph.tsx`) during dual-arm transit | M5 | R5, AC-8 |
| 21 | Kitchen Quick-Prompt Chips | Quick prompt buttons (`🍽️ Set Dining Table`, `🤝 Dual-Arm Bar Transfer`, `☕ Clear Cups`) in `App.tsx` | M5 | R5, AC-8 |
| 22 | Clean TypeScript Build | Verification that `gemini_web_gui` builds cleanly via `npm run build` with 0 errors | M5 | R5, AC-9 |
| 23 | E2E Test Suite (Tiers 1-4) | Comprehensive opaque-box test harness covering all features across 4 tiers with `TEST_READY.md` | E2E | AC-1 to AC-9 |
| 24 | Final Acceptance & Adversarial Hardening | 100% E2E test pass + Tier 5 adversarial stress testing + Forensic integrity audit | Final | AC-1 to AC-9 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Test Suite Creation | Automated test harness & test cases (Tiers 1-4) publishing `TEST_READY.md` | none | DONE |
| M1 | Standalone Kitchen Sim Scene | `isaacsim_scripts/kitchen_three_robot.py`, table, dishes, cups, long bar, camera, `/tf` | none | DONE |
| M2 | Single-Arm Kitchenware Primitives | `multi_robot_controller.py`: `KITCHEN_AFFORDANCES`, plates, cups, table clearing | none | DONE |
| M3 | Dual-Arm Collaborative Manipulation | `multi_robot_controller.py`: virtual rigid trajectory, 11-phase sync state machine, mutex | M2 | DONE |
| M4 | Gemini VLA Cognitive Loop & Tools | `gemini_robotics_node.py`, `gemini_prompts.py`, `gemini_tools.py`, `gemini_utils.py` | M2, M3 | DONE |
| M5 | Web Dashboard & Visualizer | `gemini_web_gui`: SceneMap kitchen tokens, dual-arm graph linkage, quick chips, build | M3 | DONE |
| Final | Full E2E Pass & Adversarial Hardening | 100% E2E test pass (Tiers 1-4) + Tier 5 adversarial stress testing + Forensic Audit | E2E, M1-M5 | DONE |

## Interface Contracts
### `isaacsim_scripts/kitchen_three_robot.py` ↔ ROS 2 Environment
- **Topics Published**:
  - `/tf` (`tf2_msgs/TFMessage`): Dynamic transforms for `/Dish1`, `/Dish2`, `/Dish3`, `/Cup1`, `/Cup2`, `/Cup3`, `/LongBar1`, and robot bases.
  - `/overhead_camera/rgb` (`sensor_msgs/Image`): RGB feed from overhead nadir camera.
  - `/overhead_camera/depth` (`sensor_msgs/Image`): Depth buffer feed.
  - `/overhead_camera/camera_info` (`sensor_msgs/CameraInfo`): Intrinsics.
  - `/clock` (`rosgraph_msgs/Clock`): Simulation clock.
- **Robot Joint State & Command Interfaces**:
  - Subscribes: `/fr3_1/joint_commands`, `/fr3_2/joint_commands`, `/fr3_3/joint_commands` (`sensor_msgs/JointState`).
  - Publishes: `/joint_states` or `/fr3_{id}/joint_states` (`sensor_msgs/JointState`).

### `gemini_robotics_node.py` ↔ `multi_robot_controller.py`
- **Action Command (`/gemini/action`, `std_msgs/String` JSON)**:
  - Single-Arm: `{"action": "pick"|"place"|"place_relative", "robot": "FR3_1", "target": "Dish1"|"Cup1", ...}`
  - Dual-Arm: `{"action": "dual_carry", "robots": ["FR3_1", "FR3_2"], "object": "LongBar1", "destination": [x, y, z], "sync_mode": "rigid_body"}`
- **Action Result (`/gemini/action_result`, `std_msgs/String` JSON)**:
  - `{"robot": "FR3_1"|"DUAL_FR3_1_FR3_2", "action": "...", "status": "SUCCESS"|"FAILURE", "message": "..."}`

### `multi_robot_controller.py` ↔ `gemini_web_gui`
- **Telemetry (`/multi_robot/robot_metrics`, `std_msgs/String` JSON)**:
  - Fields: `{"robots": {"1": {"state": "..."}, "2": {"state": "..."}, "3": {"state": "..."}}, "center_occupied_by": "DUAL_FR3_1_FR3_2", "collaborative_active": true, "collaborative_pair": ["FR3_1", "FR3_2"], "collaborative_object": "LongBar1"}`

## Code Layout
- `isaacsim_scripts/`:
  - `three_robot_tower.py`: UNTOUCHED baseline tower demo.
  - `kitchen_three_robot.py`: Dedicated standalone kitchen manipulation simulation scene (R1).
- `wsl_ws/src/isaac_ros2_control/isaac_ros2_control/`:
  - `multi_robot_controller.py`: Extended with `KITCHEN_AFFORDANCES` (R2) and dual-arm synchronized state machine (R3).
  - `kinematics.py`: Franka FR3 DH parameters and DLS IK solver.
  - `gemini_robotics_node.py`: VLA cognitive dispatch loop for single-arm and dual-arm actions (R4).
  - `gemini_prompts.py`: Spatial Architect & Agility Optimizer prompt templates with kitchen affordance rules (R4).
  - `gemini_tools.py`: Tool taxonomy declarations including `dual_arm_transport` (R4).
  - `gemini_utils.py`: Coordinate frames, math helpers, and `resolve_object_key` fix (R4).
- `gemini_web_gui/`:
  - `src/components/SceneMap.tsx`: 2D SVG kitchen object tokens (R5).
  - `src/components/AgentWorkflowGraph.tsx`: Dynamic dual-arm collaborative linkage edge (R5).
  - `src/App.tsx`: Quick prompt action chips for kitchen tasks (R5).
- `tests/e2e/`:
  - Dedicated E2E automated test suite and test runner created by E2E Testing Track.
