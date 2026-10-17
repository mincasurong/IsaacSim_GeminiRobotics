# KNOWLEDGE BASE

## OVERVIEW
React 19 + @xyflow/react v12 Digital Twin and Express backend for Isaac Sim / Gemini cross-OS control.

## STRUCTURE
```
gemini_web_gui/
├── src/
│   ├── App.tsx
│   └── components/
│       └── VisualWorkflowBuilder.tsx
└── server.cjs
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| React UI | `src/` | Runs on :5173, connects to WSL2 rosbridge |
| Visual Flow DAG | `src/components/VisualWorkflowBuilder.tsx` | Zero-Token execution and VLA chat |
| Express server | `server.cjs` | Runs on :3001, spawns WSL2 processes |

## ANTI-PATTERNS (THIS PROJECT)
- Do not add heavy backend logic here; defer robotic operations to ROS 2 in WSL2.
