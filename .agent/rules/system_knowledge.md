---
name: "IsaacSim Gemini System Knowledge"
description: "Core architectural knowledge of the Isaac Sim + Gemini VLA robotics project."
---

# 🤖 System Design & Architecture Knowledge

You are acting within the **IsaacSim_Gemini** repository. This project is a complex, cross-platform, multi-robot Vision-Language-Action (VLA) orchestration framework. Keep the following architectural constraints and patterns in mind when writing code, debugging, or designing new features.

## 1. Network & Platform Architecture
*   **Isaac Sim (Simulation)**: Runs on **Windows 11** (Host). Provides the physics, rendering, and camera sensors. Scripts are located in `isaacsim_scripts/`.
*   **ROS 2 Jazzy (Control)**: Runs in **WSL2 (Ubuntu 24.04)**. Nodes are built using `colcon` in `wsl_ws/`.
*   **Bridge Layer**: **FastDDS Unicast** bridges the Windows-WSL2 gap, allowing Isaac Sim (via `omni.isaac.ros2_bridge`) to talk to ROS 2.
*   **Web GUI**: A React + Express dashboard running in `gemini_web_gui/`, which connects to ROS 2 (via `rosbridge_server`) and allows user prompting.

## 2. Robotics & VLA Framework
*   **Robots**: 3x Franka FR3 cooperative robot arms.
*   **Task**: Building complex geometries (towers, pyramids, shapes) on a central target table, transferring blocks from source tables.
*   **Agentic Orchestration** (`gemini_robotics_node.py`):
    *   **Turn 1: Robotics Orchestrator**: Parses user goals and drafts the block-sequence logic.
    *   **Turn 2: Spatial Architect**: Draws a chain-of-thought ASCII grid of the desired shape, designates a central anchor block (placed at 0,0), and assigns all subsequent blocks using **Relative Placements** (`on_top_of`, `left_of`, `right_of`, `front_of`, `back_of`).
    *   **Turn 3: Safety Verifier**: Validates kinematics, speed, and safety rules.
*   **Tools**:
    *   `place`: Absolute placing.
    *   `place_relative`: Used by the AI to describe relations, while the backend ROS TF tree dynamically computes exact Cartesian offsets.

## 3. Control & Execution Loop
*   **Controller Node** (`multi_robot_controller.py`): A 50Hz FSM that subscribes to `/gemini/action`.
*   **Kinematics**: Uses Damped Least Squares Inverse Kinematics (IK) combined with Joint 1 Null-Space Projection to avoid joint limits and singularities.
*   **Locks**: Ensure `center_occupied_by` lock is respected and cleared on resets/interrupts.

## 4. Development Workflow
*   **Building**: ROS 2 code must be compiled via `wsl bash -c "cd ~/catkin_ws && source /opt/ros/jazzy/setup.bash && colcon build"`.
*   **Frontend**: React GUI hot-reloads on save.

Always respect this multi-layered setup (Windows -> WSL2 -> ROS2 -> LLM) when modifying logic or diagnosing issues.
