# ISAAC SIM SCRIPTS KNOWLEDGE BASE

## OVERVIEW
Standalone Windows Isaac Sim 6.0 OpenUSD scene builders and OmniGraph ROS 2 bridge runners (Score: 12 — distinct domain: Kit 110 / PhysX GPU simulation host).

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Mode 1: 3-arm 9-block tower scene | `three_robot_tower.py` | 240 Hz GPU TGS physics, `R` reset, `P` adversarial push (`request_adversarial_push`) |
| Mode 2: Build mobile manipulator USD | `assemble_industrial_mobile_manipulator.py` | Headless stage builder saving `industrial_mobile_manipulator_scene.usd` |
| Mode 2: Run mobile manipulator | `run_industrial_mobile_manipulator.py` | Loads composed USD (`carter_v1`/`nova_carter` + FR3) with Twist & Odometry graphs |
| Modes 5 & 6 (Private Research) | `../private/research/isaacsim_scripts/{conveyor_dual_robot,assembly_dual_robot}.py` | Relocated to `private/research/` and auto-resolved by `scripts/launcher.bat` |
| Mirror target in Isaac Sim build | `D:\git\isaacsim\src\isaacsim\source\standalone_examples\api\isaacsim.ros2.bridge\` | Keep standalone scripts synchronized when launching from Kit build tree |
| Composed mobile manipulator stage | `industrial_mobile_manipulator_scene.usd` | Saved OpenUSD stage referenced by `run_industrial_mobile_manipulator.py` |

## CONVENTIONS
- **Pre-Load `tinyxml2.dll` Before `SimulationApp`**: Load `exts\isaacsim.ros2.core\jazzy\lib\tinyxml2.dll` (92 KB) via `ctypes.WinDLL` at file top before `SimulationApp` loads `omni.kit.asset_converter`'s 104 KB `tinyxml2.dll` (prevents `fastrtps-2.14.dll` stack overflow).
- **Strip Custom CLI Flags Before Kit Init**: Parse `--mobile-base`, `--environment`, `--enable-cameras`, `--test`, and `--headless` with `parser.parse_known_args()` and set `sys.argv = [sys.argv[0]] + unknown_args` before instantiating `SimulationApp`.
- **Physics Material Binding**: Bind `UsdShade.Material` + `UsdPhysics.MaterialAPI` (`staticFriction=1.2`, `dynamicFriction=1.0`) to manipulands and `fr3_leftfinger`/`fr3_rightfinger` using `UsdShade.Tokens.weakerThanDescendants` (`"physics"`).
- **Articulation & Pose Reset Ordering**: Initialize and reset articulations (`reset_robot_articulation`, `reset_rigid_body`) only after `world.reset()` and stage hierarchy stabilization.
- **Robot TF Prefixing**: Route every arm through `configure_robot_tf_names(robot_prim_path, prefix)` so `/tf` frames stay namespaced (`fr3_1`, `fr3_2`, `fr3_3`).
- **Opt-In Camera Graph**: Construct `/overhead_camera/{rgb,depth,camera_info}` render products in `setup_overhead_camera_publishing()` only when `--enable-cameras` is active.
- **Workbench & Manipuland Tuning**: Configure 300g rigid blocks with GPU broadphase and TGS solver (`three_robot_tower.py`) to prevent inter-layer penetration under 3-arm stacking.
- **Conveyor Kinematic Velocity Control**: Use `set_rigid_velocity()` / `get_rigid_velocity()` in `conveyor_dual_robot.py` to drive deterministic belt motion for Flying Grasp interception.
- **Mobile Base & Environment Matrix**: Select `--mobile-base` (`carter_v1`, `nova_carter`) and `--environment` (`simple_room`, `warehouse`, `office`, `hospital`) via `MOBILE_BASES` and `ENVIRONMENTS` dicts.

## ANTI-PATTERNS
- **Never Overwrite Mass/Inertia Sentinels on Collision Links**: In `UsdPhysics.MassAPI`, `mass = 0.0` and `diagonalInertia = (0, 0, 0)` trigger mesh auto-computation on `fr3_link0..7`, `fr3_hand`, `fr3_leftfinger`, and `fr3_rightfinger`. Apply `mass = 1e-4, diagonalInertia = (1e-6, 1e-6, 1e-6)` ONLY to massless virtual frames (`fr3_link8`, `fr3_hand_tcp`).
- **No Re-Entrant `simulation_app.update()` in Callbacks**: Keyboard (`on_keyboard_event`), UI, and `/reset_simulation` callbacks must only set flags via `request_reset()` / `request_adversarial_push()`; execute `reset_simulation()` and `adversarial_push()` inside the main step loop between `simulation_app.update()` ticks.
- **Never Mutate Rigid Poses While Articulation Grip Holds**: Zero linear/angular velocities (`set_rigid_velocity`) and open fingers before teleporting blocks in `reset_rigid_body()`.
- **Never Hardcode Asset Root Paths**: Resolve `/Isaac/...` assets through `get_assets_root_path()` so scenes remain portable across local and Nucleus mounts.
- **No Direct `omni.usd` Imports Before Kit Bootstrap**: Keep all `omni.*`, `pxr`, and `isaacsim.core.*` imports below `simulation_app = SimulationApp(CONFIG)`.
- **No Unfiltered `sys.argv` Passthrough to Kit**: Passing custom scene arguments directly into `SimulationApp` triggers unrecognized-flag startup errors in Kit.
- **Never Poll Camera Render Products When Disabled**: Guard `setup_overhead_camera_publishing()` behind `--enable-cameras` to avoid unnecessary RTX render-product overhead during headless IK benchmarks.
- **Never Desynchronize Standalone Mirror**: Editing a scene in `isaacsim_scripts/` without syncing to `source\standalone_examples\api\isaacsim.ros2.bridge\` leaves direct Kit build launches stale.

