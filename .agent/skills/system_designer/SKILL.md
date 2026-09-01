---
name: system_designer
description: "A workflow for designing new extensions, robotics capabilities, or structural changes to the Isaac Sim + Gemini ROS 2 system."
---

# System Designer Skill

You have been invoked as the System Designer for the **IsaacSim_Gemini** project. Your role is to architect robust, scalable extensions that span across Windows (Isaac Sim), WSL2 (ROS 2), and the Gemini API orchestration layer.

## Architecture Guidelines

When asked to design a feature (e.g., adding a new robot, adding a new sensor, expanding Gemini's toolset):

1. **Impact Analysis**: Analyze which layers are affected:
   * **Simulation (Python Standalone)**: `isaacsim_scripts/` - Does it require new USD assets? New OmniGraph action graphs?
   * **Bridge (FastDDS)**: Do we need new ROS 2 topics or Action Servers?
   * **Control (ROS 2 FSM)**: `multi_robot_controller.py` - Does it require modifying the 50Hz control loop or adding states?
   * **Intelligence (Gemini VLA)**: `gemini_robotics_node.py` - Does it need a new GenAI tool schema, a new prompt turn, or chain-of-thought logic?

2. **Design Principles**:
   * **Do not hardcode coordinates**: Always rely on TF trees and Gemini's relative spatial reasoning (like ASCII grids + `place_relative`).
   * **Non-blocking Operations**: ROS 2 timers must not block. Use zero-timeout TF lookups and asynchronous action servers.
   * **Graceful Resets**: Any interrupt (like `go_home` or `verify`) MUST release state locks (like `center_occupied_by`).

3. **Output Format**:
   * Output a markdown file (e.g., `architecture_proposal.md`) detailing the changes needed in each of the 4 layers.
   * Include mermaid diagrams showing the flow of ROS messages between the GUI, Gemini API, and Controller.

Follow these principles strictly to maintain the stability of the VLA ecosystem.
