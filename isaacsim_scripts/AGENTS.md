# OVERVIEW
Standalone NVIDIA Isaac Sim 6.0 (Kit 110) Python simulation scenes, mirrored identically in `D:\git\isaacsim\src\isaacsim\source\standalone_examples\api\isaacsim.ros2.bridge\`.

## WHERE TO LOOK
| Script | Mode | Active Robots & Scene Details |
|--------|------|-------------------------------|
| `three_robot_tower.py` | Mode 1 | 3x Franka FR3 on `/MainTable` ($Z=0.20\text{m}, R=0.45\text{m}$), 3 source tables ($R=1.05\text{m}$), central `/TargetTable` ($Z=0.30\text{m}$), 9 randomized blocks |
| `conveyor_dual_robot.py` | Mode 5 | 2x FR3 at $X=\pm 0.7\text{m}$, continuous $+X$ conveyor belt, `/BufferTable` at $[0.0, 0.25, 0.16]$, bimanual `LongBar` (0.8m) & `HeavyEnginePart` |
| `assembly_dual_robot.py` | Mode 6 | 2x FR3 cooperative sub-assembly and multi-part staging (ATAMP skill library) |
| `assemble_industrial_mobile_manipulator.py` / `run_industrial_mobile_manipulator.py` | Mode 2 | OpenUSD composition & runtime for Nova Carter AMR base + Franka FR3 manipulator |

## CONVENTIONS & ANTI-PATTERNS
- **Strict Import Order**: `from isaacsim.simulation_app import SimulationApp` and `simulation_app = SimulationApp(CONFIG)` MUST precede `import numpy`, `import omni.*`, and `from pxr import ...` so Kit mounts its internal `pip_prebundle` (NumPy 2.3.1).
- **PhysX Stability (RTX 2080 Ti 11GB)**: `EnableGPUDynamicsAttr` is set to `False` with `MBP` broadphase and `PGS` solver to avoid first-tick GPU pool exhaustion across 3x FR3 articulations; robot `fr3_link0` bases use dynamic rigid bodies anchored via `UsdPhysics.FixedJoint` (`world_fixed_anchor`).
- **Deferred Articulation & Camera Init**: Initialize `Articulation` views on `frame_count == 0` after `timeline.play()`, and keep overhead cameras opt-in (`--enable-cameras`) to avoid first-tick Hydra render-product access violations.
- **TF Publishing (`ROS2PublishTransformTree`)**: Apply `isaac:nameOverride` via `configure_robot_tf_names` to prevent link name collisions, and pass ONLY articulated roots and dynamic rigid bodies (`Block1..9`) to `targetPrims`—never static table cubes (causes Fabric `getObjectType eInvalid` warnings).
