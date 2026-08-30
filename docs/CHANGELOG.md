# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
