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
