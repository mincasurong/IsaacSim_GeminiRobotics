# KNOWLEDGE BASE

## OVERVIEW
Isaac Sim 6.0 standalone Python scenes configuring OmniGraph to communicate with ROS 2 over FastDDS.

## STRUCTURE
```
isaacsim_scripts/
├── three_robot_tower.py
├── conveyor_dual_robot.py
└── assembly_dual_robot.py
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Isaac Sim scenes & OmniGraph | `*.py` | Synced with `isaacsim.ros2.bridge` |

## CONVENTIONS
- Isaac Sim Import Order: `from isaacsim.simulation_app import SimulationApp` and `simulation_app = SimulationApp(CONFIG)` MUST execute before `import numpy`, `import omni.*`, or `from pxr import ...` so Kit mounts its internal `pip_prebundle`.

## ANTI-PATTERNS (THIS PROJECT)
- No In-Process `rclpy.Node` in Sim Scripts: Never instantiate an `rclpy.Node` inside Isaac Sim Windows scripts alongside `isaacsim.ros2.bridge` (causes dual-context FastDDS access violations); use OmniGraph nodes exclusively.
- Never Overwrite `m=0.0` or `i=(0,0,0)` on Real FR3 Links or Fingers: In OpenUSD `UsdPhysics.MassAPI`, `mass = 0.0` and `diagonalInertia = (0, 0, 0)` are the auto-compute sentinels for links with `/collisions` meshes (`fr3_link0..7`, `fr3_hand`, `fr3_leftfinger`, `fr3_rightfinger`). Only apply `mass = 1e-4, diagonalInertia = (1e-6, 1e-6, 1e-6)` to the massless virtual frames `("fr3_link8", "fr3_hand_tcp")`.
- Always Bind Physics Friction Materials: Define `UsdShade.Material` + `UsdPhysics.MaterialAPI` (`staticFriction=1.2, dynamicFriction=1.0`) and bind to blocks/objects and `fr3_leftfinger`/`fr3_rightfinger` via `UsdShade.MaterialBindingAPI.Apply(prim).Bind(mat, UsdShade.Tokens.weakerThanDescendants, "physics")`.
- No Re-Entrant `simulation_app.update()` in UI/Keyboard/ROS Callbacks: Always defer resets via `request_reset()` (`_pending_reset = True`) and execute in the main loop between `simulation_app.update()` ticks.
- Kill Zombie `kit.exe` before starting a new simulation.
