# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-09-20

### Added
- **Kitchen Manipulation Environment** (`isaacsim_scripts/kitchen_three_robot.py`, 934 lines):
  - Standalone procedural kitchen scene with 3 Franka FR3 robotic arms at equilateral positions.
  - 100% self-contained rigid-body kitchen assets (no external USD/Nucleus downloads):
    - 3× Flat Dishes/Plates: 72mm diam × 18mm, 0.18 kg, rim-pinch grasp mode.
    - 3× Cups/Mugs: 62mm diam × 85mm, 0.15 kg, cylindrical-clamp grasp mode.
    - 1× Oversized Long Bar (440mm × 46mm × 26mm, 0.65 kg) spanning FR3_1 + FR3_2 reach.
  - Calibrated physics materials: static friction μ_s ≥ 1.0, dynamic μ_d ≥ 0.85.
  - Synthetic overhead RGB-D camera: `/overhead_camera/rgb`, `/depth`, `/camera_info`.
  - Dynamic `/tf` OmniGraph ActionGraph for all objects and robot bases.
  - `--test` and `--headless` CLI flags for CI/CD pipelines.
- **Kitchenware Affordance Taxonomy** (`KITCHEN_AFFORDANCES` in `multi_robot_controller.py`):
  - Per-type grasping params: approach height, grasp Z offset, gripper travel, lift height, place Z offset.
  - `dish` → rim_pinch; `cup` → cylindrical_clamp; `block` → top_down_symmetric; `long_bar` → dual_clamping.
  - `CLEARING_ZONES` and `DINING_ORGANIZATION_LAYOUT` for predefined place-setting coordinates.
- **11-Phase Synchronized Dual-Arm Collaborative Manipulation** (`multi_robot_controller.py`):
  - State machine for FR3_1+FR3_2 (or FR3_2+FR3_3) to simultaneously grasp opposite ends of the long bar.
  - Synchronized approach → contact verification → rigid-body lift → coupled Cartesian transport → release.
  - MoveIt quintic polynomial trajectory with DLS elbow null-space IK bias.
  - Mutex token `DUAL_FR3_1_FR3_2` prevents collision with single-arm tasks.
- **VLA Gemini Kitchen Extension** (M4):
  - `gemini_tools.py`: New `dual_arm_transport` function declaration (robots pair, object label, destination, sync_mode).
  - `gemini_utils.py`: `resolve_object_key()` with punctuation normalization and alias resolution.
  - `gemini_prompts.py`: Kitchen affordance rules for Spatial Architect and Agility Optimizer.
  - `gemini_robotics_node.py`: Coordinated dual-arm action dispatch with reverse-keyed pair handling.
- **Web Dashboard Kitchen Integration** (M5):
  - `SceneMap.tsx`: Live 2D SVG kitchen object tokens (dishes, cups, long bar) with `/tf` world-to-SVG projection.
  - `AgentWorkflowGraph.tsx`: Dashed purple animated edge between FR3_1 and FR3_2 during dual-arm co-transport.
  - `App.tsx`: Kitchen quick prompt chips (`🍽️ Set Dining Table`, `🤝 Dual-Arm Bar Transfer`, `☕ Clear Cups`) with 300ms debounce.
  - Collaborative dual-arm header badge showing active object during long-bar transport.
  - `/tf` and `/gemini/detected_objects` real-time ROS 2 topic subscriptions.
- **250-Test E2E Suite** (`tests/`): Four-tier test pyramid covering unit, integration, E2E, and boundary/property-based tests.

## [0.4.0] - 2026-09-20


### Added
- **Interactive React Flow v12 Agent Workflow Graph**:
  - Implemented `@xyflow/react` v12 visual canvas (`AgentWorkflowGraph.tsx`) with 5 specialized node types:
    - `GoalNode`: Active natural language mission tracker.
    - `AgentPersonaNode`: Dynamic cards for Orchestrator (🦾), Spatial Architect (📐), and Agility Optimizer (⚡) with speaking state glows.
    - `RobotArmNode`: Real-time hardware telemetry for FR3_1, FR3_2, FR3_3 tracking operational phase, utilization %, and active block target.
    - `MutexNode`: Central table collision arbiter monitor showing real-time `LOCKED [FR3_x]` vs `IDLE / FREE` mutex states.
    - `ConstructionNode`: Live tower stacking progress and height counters.
  - Animated particle edge traces reflecting real-time communication and physical arm operations.
  - Integrated MiniMap, zoom controls, and canvas navigation.
- **Glassmorphic Lab UI Redesign**:
  - Elevated dark obsidian aesthetic with frosted backdrop blur (`backdrop-filter: blur(12px)`), neon borders, and glowing status badges.
  - Tabbed Dashboard Switcher providing instantaneous toggling between:
    1. `[🔀 Workflow Graph]` (default interactive canvas)
    2. `[🗺️ 2D Workspace]` (SVG digital twin)
    3. `[⏱️ Gantt]` (execution & contention timeline)
    4. `[📊 KPIs & Trace]` (utilization bars & discrete event logs)
  - Quick Prompt chips above the chat input for rapid one-click testing of geometric formations (`⚡ Fast 9-Layer Tower`, `📐 3x3 Coplanar Grid`, `🔺 Triangle Pyramid`, `🔄 Table 1 to 3 Relay`).
  - Monospace font formatting in chat message cards for ASCII spatial reasoning grids.
- **Agility & Performance Optimizer (⚡)**:
  - Transformed Turn 3 from a restrictive safety verifier into an open-minded Agility & Performance Optimizer.
  - Grounded multi-agent reasoning in the fact that low-level ROS 2 mutex locks (`center_occupied_by`) and DLS null-space kinematics already prevent hardware collisions, enabling the agents to command `speed='fast'` and bold parallel arm actions.
  - High-velocity motion dynamics: `speed='fast'` now executes in 20 steps/phase (0.4s per motion segment at 50Hz, down from 30); default tool dispatch speed upgraded to `fast`.

## [0.3.0] - 2026-09-18

### Added
- **Publication-Grade Scientific Benchmarking & Evaluation Suite**:
  - Grounded in robotics VLA literature protocols (SayCan, RoCo, SMART-LLM, BiGym) to support arXiv publications.
  - **7 Standardized Benchmark Scenarios** (`experiment_scenarios.py`) across 5 difficulty tiers:
    - `S1`: Single-Robot Primitive Pick & Place (1 block).
    - `S2`: 3-Robot Cooperative 3-Layer Tower (3 blocks).
    - `S3`: Full 9-Block Monolithic Cooperative Tower (9 blocks).
    - `S4`: 3×3 Coplanar Square Grid Formation (9 blocks).
    - `S5`: Coplanar Triangle / Pyramid Formation (6 blocks).
    - `S6`: Cross-Table Staging & Relay Transfer (2 blocks).
    - `S7`: Dynamic Disturbance Recovery (6 blocks).
  - **Automated Batch Trial Runner** (`experiment_runner.py`): Automated environment reset (`/multi_robot/reset`), trial sequencing, timeout handling, ground-truth TF verification, and rule-based baseline comparison (`--baseline`).
  - **Telemetry Experiment Logger** (`experiment_logger.py`): Captures 35+ metrics across Task-Level (TSR, GCR, makespan), Coordination (Gini workload balance, center lock contention), Physical Execution (pick/place success, TF displacement error), and LLM VLA throughput.
  - **Publication Analytics & Plot Generator** (`analyze_experiments.py`): Automatically computes statistics (Wilson score 95% CIs) and compiles publication-ready LaTeX tables (`table1_success_rate.tex`, `table2_timing_breakdown.tex`, `table3_robot_coordination.tex`) and vector figures (`fig2_success_rate.pdf`, `fig3_utilization_heatmap.pdf`).
- **Spatial Architect (📐) & Relative Placement API**:
  - Added 2D ASCII Grid Chain-of-Thought (CoT) reasoning for spatial layout generation.
  - Added `place_relative` function calling tool for grid, offset, and relative coordinate placement.
  - Ground-truth TF distance injection for proximity-first grasping and real-time workspace state tracking (`workspace_state.py`).

## [0.2.0] - 2026-08-30

### Added
- **Salabim-Inspired Industrial Dashboard Upgrade**: Refactored the React web dashboard into a modular architecture with four new monitoring tabs:
  - **KPI Dashboard**: Real-time robot resource utilization tracking (busy/idle %), state badges, and task success/failure counters.
  - **Enhanced Gantt Chart**: Improved timeline visualization with queue/waiting time segments (for mutex locks), time axis ticks, and zoom controls.
  - **2D Scene Map**: Lightweight SVG digital twin providing a top-down view of all 9 block tokens, 3 robot arms, and target tower growth.
  - **Event Trace Table**: Filterable and sortable discrete event logging table with task duration calculation and CSV export.
- **ROS 2 Metrics Publisher**: New `/multi_robot/robot_metrics` topic (2Hz) in `multi_robot_controller.py` to stream live utilization and state machine tracking data to the frontend.

## [0.1.0] - 2025-08-23

### Added
- 3x Franka FR3 cooperative tower stacking simulation (Isaac Sim 4.5+ / 6.0)
- Gemini Robotics-ER VLA orchestration with Function Calling and agentic loop
- Autonomous rule-based 9-block tower motion planner (no API required)
- Damped Least Squares (DLS) Inverse Kinematics with Null-Space projection
- ChatGPT-style web dashboard (React + Express) with dark theme
- Live Gantt chart timeline for multi-robot task visualization
- Voice input (Web Speech API) and natural language goal dispatch
- Color-coded ROS 2 `/rosout` log streaming in the browser
- Integrated WSL2 terminal output viewer
- One-click `colcon build` from the web dashboard
- FastDDS Unicast bridge for Windows ↔ WSL2 cross-OS communication
- Automated WSL2 + ROS 2 Jazzy setup scripts (`setup_all.sh`)
- One-click system launcher (`start_dashboard.bat`)
- Mobile manipulation demo (Nova Carter + FR3)
- Dynamic block pose randomization on simulation reset
- Overhead synthetic camera (RGB + Depth) for VLM scene understanding
