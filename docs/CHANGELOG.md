# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2026-10-05

### Added
- **Interactive Parallel Task Blocks Canvas (`@xyflow/react`)**:
  - Implemented `VisualWorkflowBuilder.tsx` providing visual drag-and-drop task blocks (`Pick`, `Place`, `Dual Pick`, `Circle Wave`, `Dual Place`, `Home`) with live in-block parameter selectors for robots, targets, coordinates, and speed.
  - **True Parallel DAG Execution**: Asynchronous wavefront scheduler executing independent branches concurrently (e.g. 3-arm concurrent pick) and synchronizing at physical barriers (e.g. center table mutex).
  - **Real Hardware Feedback Verification**: Subscribes to `/gemini/action_result` and strictly awaits physical completion before advancing. Actions halting immediately upon failure to prevent cascading hardware collisions.
  - **Inline Edge Removers & Half-Moon Ports**: Sleek frosted translucent ports with 40px magnetic snap and inline `✕` wire-remover buttons for instant edge deletion.
  - **Natural Language to DAG Generator (`/api/workflow/generate`)**: Automated parallel multi-arm workflow synthesis powered by `gemini-3.5-flash-lite`.
- **Dual Execution Engine Toggle**:
  - Added navbar switcher for `🧩 Visual Flow Mode (Zero-Token)` (100% deterministic 50 Hz ROS 2 execution) and `🧠 Autonomous VLA Mode` (closed-loop multimodal Gemini ER2 reasoning).
  - Adaptive screen layout: Left chat pane automatically collapses in Visual Flow mode to maximize canvas space, and opens in Autonomous VLA mode.
- **Gemini Model Transition (`gemini-3.5-flash-lite`)**:
  - Switched `PLANNER_MODEL` default to `gemini-3.5-flash-lite` (4M TPM quota, isolated from coding agent session).
- **Operator Feedback & Self-Evolution Loop**:
  - Integrated operator feedback console in `SystemMonitor.tsx` logging observations to `logs/monitoring/user_feedback.jsonl`.
  - Added `feedback_evolution_engine.py` diagnosing systemic failure modes against telemetry and proposing parameter and skill governance tuning.
- **Mode 5 Coordinated Placement & Kinematics**:
  - Refactored `DualArmPlaceTrajectory` with independent arm step counters (`step1`, `step2`) and front buffer placement ($Y = +0.25\,\text{m}, Z = 0.35\,\text{m}$), eliminating mid-air drops and IK singularities.
  - Added automatic single-to-dual arm place promotion in `rule_based_verifier.py` and `conveyor_dual_controller.py`.

## [0.5.0] - 2026-10-05

### Added
- **Google Gemini 3.8 Flash Spatial Architect**:
  - Integrated `PLANNER_MODEL=gemini-3.8-flash` as the Tier-1 Spatial Architect across `gemini_robotics_node.py` and `conveyor_gemini_node.py`.
  - Accelerates 2D ASCII Grid Chain-of-Thought (CoT) layout reasoning and millimeter-precise coordinate generation with sub-second latency.
- **Antigravity 2.0 Autonomous Ralph Loop Integration**:
  - Added `.antigravity/permissions.json` and `.antigravity/config.json` supporting the Ralph loop autonomous pattern with auto-approved cross-platform terminal commands and file edits.
  - Implemented safe denylists protecting critical git and filesystem branches.
- **OpenCode & Native ROS 2 Model Context Protocol (MCP)**:
  - Added `opencode.json` defining the `physical-ai-orchestrator` agent persona with `google/gemini-3.8-flash`.
  - Added `.opencode/hardware_context_and_idls.md` as a deterministic static context cache invariant (saving 75–90% token overhead).
  - Built-in ROS 2 Jazzy MCP server (`wsl_ws/scripts/ros2_mcp.py`) allowing AI coding agents to introspect nodes, topics, and services.
- **Real-Time Health & Diagnostic Auditor (Gemini 3.5 Flash-Lite)**:
  - Added `monitoring_agent_node.py` with `GeminiHealthAuditor` utilizing `gemini-3.5-flash-lite` (1M token context).
  - Real-time stream auditing of `/rosout`, joint limits, pick success rates, and guardrail deny events.
- **Pre-Descent Kinematic & Collision Guardrails**:
  - Implemented deterministic reachability and collision guardrails in `rule_based_verifier.py`, automatically validating VLA actions prior to physical arm descent.
- **Conveyor Stream Dual-Robot Manipulation (Mode 5)**:
  - Added `conveyor_dual_robot.py` and `conveyor_dual_controller.py` for continuous Cartesian tracking of items on a moving PhysX conveyor belt.
  - Implemented synchronous dual-arm circular wave trajectories (`dual_arm_circle`) for long bars.

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
