# Gemini Robotics ER — Web Dashboard & Digital Twin

A futuristic, high-performance web dashboard for monitoring, controlling, and visualizing multi-robot physical AI simulations in real time.

---

## ✨ Features

- **🔀 Interactive Agent Workflow Graph** — Built on `@xyflow/react` (React Flow v12), rendering dynamic nodes for the user goal, multi-agent personas (Orchestrator 🦾, Spatial Architect 📐, Performance Optimizer ⚡), Franka FR3 robot arms, central workspace mutex locks, and physical construction targets with animated particle flow edges.
- **💬 VLA Multi-Agent Chat Interface** — Send natural language and geometric goals via text or speech (Web Speech API). Features role-colored cards, speaking agent badges, and monospace formatting for ASCII spatial reasoning grids.
- **⚡ Quick Prompt Chips** — One-click action chips for rapid testing of geometric formations (`⚡ Fast 9-Layer Tower`, `📐 3x3 Coplanar Grid`, `🔺 Triangle Pyramid`, `🔄 Table 1 to 3 Relay`).
- **🗺️ 2D Digital Twin Map** — Real-time SVG workspace visualizer tracking the positions and movements of all 9 colored blocks, 3 FR3 robot bases, reach zones, and the central target table.
- **⏱️ Enhanced Gantt Timeline** — High-precision timeline tracking parallel arm execution, pick/place phases, and shared workspace lock contention (mutex wait times).
- **📊 KPI Telemetry Dashboard** — Real-time robot resource utilization bars (busy/idle %), active state badges, and task success/failure counters.
- **📋 Event Trace Table** — Filterable, sortable discrete event log table with duration calculations and CSV export for empirical evaluation.
- **📜 ROS 2 Log Viewer & Terminal** — Live color-coded `/rosout` stream (DEBUG → FATAL) and real-time WSL2 terminal output via Server-Sent Events (SSE).
- **🛠️ Remote Simulation Control** — One-click `colcon build`, `Start`, `Stop`, and `Reset` buttons directly from the top navigation bar.

---

## 💻 Tech Stack

| Layer | Technology |
|---|---|
| **Frontend Framework** | React 19 + TypeScript + Vite |
| **Workflow Graph** | `@xyflow/react` v12 (React Flow) |
| **Icons** | Lucide React |
| **Styling** | Glassmorphic Dark Obsidian Theme (`backdrop-filter: blur(12px)`) |
| **Backend Gateway** | Express.js (Node.js) with Server-Sent Events (SSE) |
| **Robotics Middleware** | `roslibjs` via `rosbridge_server` (WebSocket on port 9090) |

---

## 🚀 Quick Setup

```bash
# Navigate to the GUI folder
cd gemini_web_gui

# Install dependencies
npm install

# Start Vite dev server (hot reload)
npm run dev

# Or build for production
npm run build
```

The accompanying Express backend (`server.cjs`) runs on port **3001** and handles:
- `/api/start` / `/api/stop` — Launches and terminates the WSL2 ROS 2 bringup processes.
- `/api/build` — Triggers `colcon build` inside WSL2 via SSE streaming.
- `/api/logs` — SSE stream for WSL2 terminal stdout/stderr.
- `/api/status` — Checks whether the backend bringup process is currently active.

---

## 🏗️ Architecture

```
Browser (localhost:5173)
  ├── React 19 Client (App.tsx)
  │   ├── AgentWorkflowGraph (@xyflow/react v12)
  │   ├── SceneMap (2D SVG Digital Twin)
  │   ├── GanttChart (Execution & Mutex Contention Timeline)
  │   ├── KpiDashboard (Resource Utilization & State Tracking)
  │   ├── EventTrace (Sortable Discrete Event Log & CSV Export)
  │   ├── WebSocket Client → ws://localhost:9090 (rosbridge_server)
  │   │   ├── /rosout (log stream)
  │   │   ├── /gemini/action (dispatched robot actions)
  │   │   ├── /gemini/action_result (action completion events)
  │   │   ├── /gemini/chat_reply (multi-agent brainstorm & VLA responses)
  │   │   ├── /gemini/custom_goal (operator mission dispatch)
  │   │   └── /multi_robot/robot_metrics (utilization & state telemetry)
  │   └── SSE Connection → http://localhost:3001/api/logs
  │       └── WSL2 terminal streaming
  └── Express Gateway (server.cjs, port 3001)
      └── child_process.spawn → WSL2 bringup.bash
```

---

## 🧭 Dashboard Tabs

The right panel features four dedicated tabs accessible via the navigation header:

1. **`[🔀 Workflow Graph]`**: Full interactive graph canvas mapping the flow from Operator Goal → Brainstorm Personas → Multi-Arm Parallel Dispatch → Mutex Collision Arbiter → Isaac Sim Construction.
2. **`[🗺️ 2D Workspace]`**: Overhead digital twin displaying live block coordinates, robot arm reach envelopes, and tower stacking heights.
3. **`[⏱️ Gantt]`**: 5 Hz real-time Gantt timeline showing execution slices and lock wait times for each robot.
4. **`[📊 KPIs & Trace]`**: Numerical performance metrics (utilization %, completed actions) and discrete event table with one-click CSV download.
