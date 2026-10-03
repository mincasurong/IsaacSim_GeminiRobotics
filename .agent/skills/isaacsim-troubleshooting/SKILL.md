---
name: isaacsim-troubleshooting
description: >-
  Lessons learned and troubleshooting guide for Isaac Sim + ROS 2 + React Flow architectures, 
  including TF timeouts, invisible nodes, and colcon pathing.
---

# Isaac Sim & Gemini Workspace Troubleshooting

## 1. ROS 2 Execution & TF Timeouts
**Anti-Pattern**: Using `timeout=Duration(...)` in `tf_buffer.lookup_transform()` inside high-frequency timer callbacks (50Hz+) on a single-threaded executor.
**Fix**: This starves incoming state topics. Always use non-blocking cache lookups:
`trans = self.tf_buffer.lookup_transform(frame, name, rclpy.time.Time())`

## 2. React Flow v12 High-Frequency Rendering
**Anti-Pattern**: Relying solely on CSS for custom node dimensions in `@xyflow/react` v12.
**Fix**: If nodes are subjected to rapid state updates (like ROS telemetry), they will unmount or render as `visibility: hidden` because the state updates faster than the DOM `ResizeObserver`. Always assign static numeric `width` and `height` properties directly in the `nodes` array objects.

## 3. Python `pathlib` Indexing in Colcon
**Anti-Pattern**: Using hardcoded `parents[N]` (e.g., `Path(__file__).parents[7]`) to locate the workspace root.
**Fix**: `colcon build` symlinks or copies files into `build/` and `install/` directories, changing the folder depth. Always use a safe upward loop (`for parent in current_file.parents:`) to locate `.env` files or project roots.

## 4. Multi-Robot Spatial Mutual Exclusion & Mid-Air Collisions
**Anti-Pattern**: Releasing the shared center workspace lock at the beginning of `RETURN_HOME` while the manipulator arm is still physically sweeping through the center staging zone.
**Fix**: Gate the transition into center workspace states (`WAIT_FOR_CENTER -> TUCK_AFTER_PICK`) with both the lock check AND an invariant check ensuring no other robot is currently in ANY center-traversing state (`CENTER_WORKSPACE_STATES`). Only release `center_occupied_by` when `RETURN_HOME` has fully completed.

## 5. Isaac Sim PhysX Gripper Dwell Dynamics
**Anti-Pattern**: Setting gripper dwell duration to $\le 5$ ticks ($< 100$ ms) at 50 Hz.
**Fix**: Franka parallel fingers require 250–350 ms under PhysX joint drive dynamics to contact a rigid block and develop normal grasp force. Always configure `dwell_steps >= 15` (at 50 Hz, $\ge 300$ ms) for `GRASP` and `RELEASE` phases.

## 6. Windowed Grasp Verification
**Anti-Pattern**: Checking `gripper_pos > 0.01` to determine grasp success. If the gripper command lagged or failed and fingers stayed wide open ($0.04$ m), this erroneously evaluates to true.
**Fix**: Check for a bounded finger window (`0.005 < gripper_pos < 0.038`). Under-travel ($< 5$ mm) indicates empty space closure; over-travel ($> 38$ mm) indicates a failed or non-actuated finger command.
