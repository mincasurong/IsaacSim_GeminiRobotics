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
- **Strict Import Order**: `from isaacsim.simulation_app import SimulationApp` and `simulation_app = SimulationApp(CONFIG)` MUST precede `import numpy`, `import omni.*`, and `from pxr import ...` so Kit mounts its internal `pip_prebundle` (NumPy 2.3.1), and preload `exts/isaacsim.ros2.core/jazzy/lib/tinyxml2.dll` via `ctypes.WinDLL` before `SimulationApp(CONFIG)` so `omni.kit.asset_converter` cannot shadow FastDDS's `tinyxml2.dll`.
- **PhysX Stability & Joint/Inertia Sanitization**:
  - Force `fr3_link0` dynamic (`physics:kinematicEnabled = False`) and align `/FR3_*/root_joint` `localPos0` / `localRot0` with each robot's world mount pose (`mount_pos`, `mount_quat`) so PhysX never logs `CreateJoint - found a joint with disjointed body transforms`.
  - Never call `robot_art.set_world_poses(...)` on fixed-base table-mounted FR3 arms during reset (causes child link `fr3_link0` to become disjointed from `/FR3_*`).
  - Sanitize `fr3_link8` and `fr3_hand_tcp` (`UsdPhysics.MassAPI`: `mass = 1e-4`, `diagonalInertia = (1e-6, 1e-6, 1e-6)`) and cap `PhysxArticulationAPI` `solverVelocityIterationCount = 4`.
- **No Re-Entrant `simulation_app.update()` in UI/Keyboard/ROS Callbacks**:
  - `omni.ui.Button` `clicked_fn` and `carb.input` callbacks execute mid-frame while `omni.rtx` is recording the GPU command list (`actualState: Recording`). Calling `simulation_app.update()` or `app_utils.play()` + `simulation_app.update()` inside a callback triggers `cmdBegin` before `cmdEnd` and crashes the Vulkan/RTX renderer.
  - Always defer resets and adversarial impulses via `request_reset()` / `request_adversarial_push()` (`_pending_reset = True`, `_pending_adversarial_push = True`) and execute them in the main `while simulation_app.is_running():` loop between `simulation_app.update()` ticks.
- **TF Publishing (`OgnIsaacComputeTransformTree` -> `OgnROS2PublishTransformTree`)**: Wire `isaacsim.core.nodes.IsaacComputeTransformTree` (`ComputeTF.inputs:targetPrims`) into `PublishTF.inputs:{parentFrames,childFrames,translations,orientations}` instead of deprecated `PublishTF.inputs:targetPrims`.
