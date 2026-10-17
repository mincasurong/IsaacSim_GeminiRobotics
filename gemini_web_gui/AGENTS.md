# OVERVIEW
React 19 + `@xyflow/react` v12 Digital Twin & Visual Task Workflow Builder (`:5173`) paired with an Express SSE/process-control backend (`server.cjs` on `:3001`).

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Main UI & ROSBridge client | `src/App.tsx` | Connects to `ws://localhost:9090` (`rosbridge_websocket`) and `http://localhost:3001` |
| Zero-Token Visual DAG Builder | `src/components/VisualWorkflowBuilder.tsx` | Parallel wavefront scheduler, half-moon ports, `/gemini/action` dispatch & `/gemini/action_result` verification |
| 2D Live TF Workspace Map | `src/components/SceneMap.tsx` | Real-time block/arm coordinate projection and elevation badges |
| Telemetry & Gantt Views | `src/components/{KpiDashboard,GanttChart,SystemMonitor,EventTrace}.tsx` | Subscribes to `/multi_robot/robot_metrics` and `/gemini/monitoring_summary` |
| WSL2 Process & Build Bridge | `server.cjs` | Spawns WSL2 `bringup.bash`, `colcon build`, `workflow_generator.py`, and `feedback_evolution_engine.py` |

## CONVENTIONS & GOTCHAS
- **Mode Mapping (`server.cjs`)**: `POST /api/start` maps GUI Mode `1` (3-Robot Tower) -> `bringup.bash` option `1`, Mode `5` (Conveyor Dual) -> option `7`, Mode `6` (Assembly ATAMP) -> option `8`.
- **Dual Execution Modes**: `flow` mode dispatches deterministic JSON actions directly to `/gemini/action` with zero LLM token usage and halts immediately on `success: false` from `/gemini/action_result`; `vla` mode publishes natural language goals to `/gemini/custom_goal`.
- **Commands**: `npm run dev` (Vite dev server on `:5173`), `node server.cjs` (Express API/SSE on `:3001`), `npm run build` (`tsc -b && vite build`).
