# Implementation Plan: Advanced Bimanual Manipulation & Dynamic Conveyor Tracking

## 1. Executive Summary
The current repository successfully implements basic multi-robot coordination (e.g., sequential tower building with a mutex) and zero-token visual workflow execution. However, as identified in the logs and user feedback, it struggles with two advanced, yet industry-standard, robotics challenges:
1. **True Bimanual Collaboration**: Handling a single rigid object (like the `LongBar`) simultaneously with two arms without inducing stress, dropping the object, or failing Inverse Kinematics (IK).
2. **Dynamic Conveyor Tracking**: Picking objects from a fast-moving conveyor belt (e.g., > 0.15 m/s) where open-loop "stop and grasp" methods fail due to the object moving out of the gripper during the descent and finger-closing phases.

This document outlines the architectural changes required to solve these issues robustly.

---

## 2. Issue #1: Multi-Robot Collaboration on a Single Object (Bimanual Manipulation)

### Current State & Failure Mode
- The `conveyor_dual_controller.py` dispatches `dual_arm_pick` by setting the state of both `FR3_1` and `FR3_2` to `INIT` and letting them run through the standard `HOVER_PICK` -> `DESCEND_PICK` -> `GRASP` -> `LIFT` state machine **independently**.
- **The Problem**: Because the arms execute independently at 50 Hz, one arm may reach the object, close its gripper, and begin lifting before the other arm has finished descending. This applies asymmetric torque to the rigid body, causing it to slip, tilt, or drop. Furthermore, independent IK solvers do not account for the closed kinematic chain constraint once both grippers are attached.

### Implementation Plan
1. **Create `DualArmPickTrajectory` Strategy**:
   - Similar to the existing `DualArmPlaceTrajectory` and `DualArmCircleTrajectory`, we need a dedicated class for bimanual picking in `conveyor_dual_controller.py`.
   - **Phase 1 (Synchronized Hover)**: Both arms compute IK for their respective hover poses. The state machine *waits* until both arms report arrival before proceeding.
   - **Phase 2 (Synchronized Descent)**: Both arms descend using a shared parameter $t \in [0, 1]$ (e.g., a quintic spline) to ensure they touch the object at the exact same millisecond.
   - **Phase 3 (Synchronized Grasp)**: Both grippers close simultaneously. A strict dwell time (e.g., 400ms) is enforced to ensure physical contact settles in the PhysX engine.
   - **Phase 4 (Synchronized Lift)**: Both arms lift the object along the Z-axis using the exact same velocity profile, maintaining the relative distance between the two end-effectors to prevent internal stress on the `LongBar`.
2. **Update Controller Routing**:
   - Intercept `dual_arm_pick` in the `_action_cb` of `conveyor_dual_controller.py`.
   - Route execution to the new `DualArmPickTrajectory` instead of the independent `_process_robot` loop.

---

## 3. Issue #2: Dynamic Pick-and-Place on Fast-Moving Conveyors

### Current State & Failure Mode
- The visual servoing logic computes a `predicted_y` based on `conveyor_speed` and a `lead_t` (time to descend).
- **The Problem**: The robot moves to this static `predicted_y` and **stops** to close its gripper. If the conveyor is moving fast (e.g., 0.15 m/s), the object continues to move while the gripper is closing (which takes ~0.12s to 0.25s). The object slides out of the finger workspace, resulting in a "ghost grasp" (closing on empty air) and a 0.0% pick success rate.

### Implementation Plan
1. **Implement Velocity Feedforward (Flying Grasp)**:
   - Instead of stopping at a predicted point, the end-effector must **match the velocity** of the conveyor belt during the descent and grasp phases.
   - Modify the target pose dynamically in the 50 Hz loop: $Y_{target}(t) = Y_{initial} + V_{conveyor} \times t$.
   - The IK solver must track this moving target continuously.
2. **Update `conveyor_dual_controller.py`**:
   - In the `DESCEND_PICK` state, continuously update `end_pos[1]` (the Y coordinate) by adding `self.conveyor_speed * dt` every control tick.
   - **Crucial**: Do not stop the arm's Y-axis motion when triggering the `GRASP` state. The arm must continue moving along the Y-axis at `conveyor_speed` while the fingers close.
   - Once the fingers are fully closed (contact verified), transition to `LIFT`, gradually decelerating the Y-axis motion while accelerating upward in Z.
3. **Restore Conveyor Speed**:
   - Revert the conveyor speed in `isaacsim_scripts/conveyor_dual_robot.py` back to the challenging `0.15` m/s to validate the dynamic tracking algorithm.

---

## 4. Execution Steps for the AI Agent
1. Read `wsl_ws/src/isaac_ros2_control/isaac_ros2_control/conveyor_dual_controller.py` to understand the current trajectory strategy pattern.
2. Implement the `DualArmPickTrajectory` class and integrate it into the `_action_cb` and `control_loop`.
3. Override or modify the `DESCEND_PICK` and `GRASP` states to support continuous velocity tracking (flying grasps) for conveyor items.
4. Update `isaacsim_scripts/conveyor_dual_robot.py` to set the conveyor speed back to `0.15` m/s.
5. Verify the Python syntax and build the ROS 2 workspace.