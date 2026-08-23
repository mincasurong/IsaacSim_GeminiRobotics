# Gemini Robotics ER — Web Dashboard

A ChatGPT-style web dashboard for monitoring and controlling the multi-robot simulation in real time.

## Features

- **Chat Interface** — Send natural language goals to the Gemini VLA agent via text or voice input
- **Live Gantt Timeline** — Visualize parallel robot task execution across all 3 Franka FR3 arms
- **Action Blocks** — See every `pick`, `place`, and `go_home` command dispatched by Gemini
- **ROS 2 Log Viewer** — Color-coded, filterable `/rosout` log stream (DEBUG → FATAL)
- **WSL2 Terminal** — Live output from `bringup.bash` and backend processes
- **Build Button** — Trigger `colcon build` inside WSL2 directly from the browser
- **Start/Stop/Reset** — Full lifecycle control of the ROS 2 backend and Isaac Sim simulation

## Tech Stack

| Layer    | Technology                          |
|----------|-------------------------------------|
| Frontend | React 19 + TypeScript + Vite        |
| Backend  | Express.js (Node.js) with SSE       |
| ROS 2    | roslibjs via rosbridge_server       |
| Styling  | Inline CSS (dark theme, no Tailwind)|

## Quick Setup

```bash
# Install dependencies
npm install

# Development mode (hot reload)
npm run dev

# Production build
npm run build
```

The backend server (`server.cjs`) runs on port **3001** and handles:
- `/api/start` / `/api/stop` — Start/stop the WSL2 bringup process
- `/api/build` — Trigger `colcon build` via SSE streaming
- `/api/logs` — Server-Sent Events stream for WSL2 terminal output
- `/api/status` — Check if the backend process is running

## Architecture

```
Browser (localhost:5173)
  ├── React App (App.tsx)
  │   ├── WebSocket → ws://localhost:9090 (rosbridge)
  │   │   ├── /rosout (log stream)
  │   │   ├── /gemini/action (dispatched commands)
  │   │   ├── /gemini/action_result (completion events)
  │   │   └── /gemini/custom_goal (send goals)
  │   └── SSE → http://localhost:3001/api/logs
  │       └── WSL2 terminal output
  └── Express Server (server.cjs, port 3001)
      └── child_process.spawn → WSL2 bringup.bash
```

## Development Notes

- The frontend connects to ROS 2 via [roslibjs](http://wiki.ros.org/roslibjs) through a `rosbridge_websocket` server running on port 9090 inside WSL2.
- ANSI escape codes from ROS 2 logs are automatically stripped before display.
- The Gantt chart updates at 5 Hz to show real-time task progress.
