# gemini_web_gui

## OVERVIEW
React 19 + `@xyflow/react` v12 Digital Twin UI (`:5173`) and Express CJS process/SSE bridge (`:3001`) for cross-OS ROS 2 orchestration (Score: 16 — distinct full-stack web & telemetry domain).

## WHERE TO LOOK
| Component / File | Location | Role & Details |
|------------------|----------|----------------|
| Express Control Bridge | `server.cjs` | Port `:3001`; endpoints `/api/{logs,status,build,start,stop,feedback,workflow/generate}` |
| App Entry & Styles | `src/main.tsx`, `src/index.css` | React 19 root mount and Tailwind CSS v4 (`@tailwindcss/postcss`) global styles |
| Dashboard Container | `src/App.tsx` | `roslib` WebSocket (`ws://localhost:9090`), SSE `/api/logs` listener, mode selector (Modes 1/5/6), tab state |
| Visual DAG Builder | `src/components/VisualWorkflowBuilder.tsx` | `@xyflow/react` v12 node editor, Zero-Token sequential/parallel DAG runner, `/api/workflow/generate` client |
| Agentic Task Graph | `src/components/AgentWorkflowGraph.tsx` | Multi-robot task decomposition and live execution phase graph |
| Spatial Digital Twin | `src/components/SceneMap.tsx` | 2D/3D workspace map rendering FR3 arm poses, block coordinates, and conveyor belt state |
| Telemetry & Anomaly UI | `src/components/SystemMonitor.tsx` | Live joint/IK telemetry, safety verifier counters, and anomaly alerts (`/gemini/monitoring_summary`) |
| Event & CSV Trace | `src/components/EventTrace.tsx` | Structured ROS 2 action/result timeline and `copyCSV` exporter |
| Execution Timeline | `src/components/GanttChart.tsx` | Multi-arm (`fr3_1..3`) task concurrency Gantt chart |
| Performance Metrics | `src/components/KpiDashboard.tsx` | Cycle time, success rate, and token-saving KPI cards (`/multi_robot/robot_metrics`) |
| Shared Tokens & Types | `src/components/theme.ts` | Palettes (`C_light`, `C_dark`), shared interfaces (`RobotAction`, `MetricsData`, `BlockData`), parsers (`stripAnsi`, `parseAction`, `parseResult`) |
| Build & Lint Configs | `vite.config.ts`, `.oxlintrc.json` | Vite 8 React plugin config and Oxlint static analysis rules |

## CONVENTIONS
- **Dual-Channel Telemetry**: Use `roslib` (`ws://localhost:9090`) for real-time ROS 2 topics (`/gemini/custom_goal`, `/gemini/action`, `/gemini/action_result`, `/gemini/chat_reply`, `/gemini/monitoring_summary`, `/gemini/summarize_logs`, `/multi_robot/robot_metrics`, `/reset_simulation`, `/rosout`) and Express SSE (`GET /api/logs` on `:3001`) for WSL2 process stdout/stderr.
- **Launcher Mode Mapping**: `server.cjs` (`POST /api/start`) translates UI mode IDs to `bringup.bash` interactive stdin options via `BRINGUP_MAP` (`Mode 1 -> 1`, `Mode 5 -> 7`, `Mode 6 -> 8`).
- **Python CLI Subprocesses**: `POST /api/workflow/generate` and `POST /api/feedback` invoke `workflow_generator.py` and `feedback_evolution_engine.py` directly on the Windows host (`../wsl_ws/src/isaac_ros2_control/isaac_ros2_control/*.py`) and parse JSON from stdout.
- **Zero-Token Workflow Execution**: `VisualWorkflowBuilder` executes approved DAG steps by publishing directly to ROS 2 action/goal topics over `rosbridge_websocket` without re-invoking the Gemini API.
- **Styling & Theme State**: Centralize color tokens, status badges (`LOG_COLORS`, `BLOCK_COLORS`, `PHASE_COLORS`), and message parsers in `src/components/theme.ts` alongside Tailwind CSS v4.
- **Frontend Commands**: Run `npm run dev` (Vite `:5173`), `node server.cjs` (Express `:3001`), `npm run build` (`tsc -b && vite build`), and `npm run lint` (`oxlint`).

## ANTI-PATTERNS
- **No Robotic Planning or IK in Node/React**: Never compute trajectories, inverse kinematics, or safety guardrails in `gemini_web_gui`; delegate all control and verification to WSL2 ROS 2 nodes.
- **No Unbounded SSE Log Buffers**: Keep `server.cjs` `logBuffer` capped at `MAX_LOG_LINES` (2000) to prevent memory leaks during 50 Hz simulation runs.
- **No Orphaned WSL2 Processes on Restart**: Always terminate existing `gemini_controller`, `rosbridge`, `multi_robot`, `conveyor`, and `bringup.bash` processes in WSL2 before spawning a new `bringup.bash` session.
- **No Legacy `reactflow` Imports**: Use `@xyflow/react` v12 named imports (`ReactFlow`, `Handle`, `Position`, `useNodesState`, `useEdgesState`); never import the deprecated `reactflow` package.
- **No Blocking Calls in Express Routes**: Spawn long-running WSL2 `colcon build` and `bringup.bash` commands asynchronously with `child_process.spawn` and stream output via `appendLog`.
- **No Hardcoded ANSI Sequences in UI State**: Strip terminal escape codes with `stripAnsi` from `src/components/theme.ts` before rendering WSL2 log lines or parsing JSON action payloads.
