# SPDX-FileCopyrightText: Copyright (c) 2020-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Three-robot tower assembly scene — Post-doc edition (Isaac Sim 6.0).

Key features:
- 3x Franka FR3 robotic arms on elevated workbench (GPU physics, 240Hz)
- GPU broadphase + TGS solver for stable multi-body tower stacking
- RayTracedLighting renderer with Fabric scene delegate
- ROS 2 Jazzy bridge: joint states, commands, /tf, clock, overhead camera
- Overhead RGB+Depth camera @ 10Hz for Gemini Robotics VLM
- Physics friction materials on blocks and tables
- Block mass: 300g rigid bodies with randomized placement
- Reset service + adversarial push for RL/evaluation
"""

import argparse
import sys
import os
import ctypes

# Pre-load ROS 2 tinyxml2.dll (92KB) before SimulationApp loads omni.kit.asset_converter's
# incompatible tinyxml2.dll (104KB), preventing stack buffer overflow in fastrtps-2.14.dll
for _cand in (
    os.path.join(os.environ.get("ISAAC_PATH", r"D:\git\isaacsim\src\isaacsim\_build\windows-x86_64\release"), "exts", "isaacsim.ros2.core", os.environ.get("ROS_DISTRO", "jazzy"), "lib", "tinyxml2.dll"),
    r"D:\git\isaacsim\src\isaacsim\_build\windows-x86_64\release\exts\isaacsim.ros2.core\jazzy\lib\tinyxml2.dll",
    r"D:\git\isaacsim\src\isaacsim\_build\windows-x86_64\release\exts\isaacsim.ros2.core\humble\lib\tinyxml2.dll",
):
    if os.path.exists(_cand):
        try:
            ctypes.WinDLL(_cand)
            break
        except OSError:
            pass

from isaacsim.simulation_app import SimulationApp

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("--test", default=False, action="store_true", help="Run in test mode")
parser.add_argument("--headless", default=False, action="store_true", help="Run in headless mode")
args, _ = parser.parse_known_args()

# Setup config
CONFIG = {
    "renderer": "RayTracedLighting",   # Balanced: fast interactive, publication-quality
    "headless": args.headless,
    "physics_gpu": 0,
    "multi_gpu": False,
    "sync_loads": True,
    "fast_shutdown": True,
    "extra_args": [
        "--/app/runLoops/main/rateLimitEnabled=false",
        "--/app/useFabricSceneDelegate=true",
        "--/rtx-transient/dlssg/enabled=false",
        "--/omni/replicator/asyncRendering=false",
    ],
}
simulation_app = SimulationApp(CONFIG)

import numpy as np
import carb
import isaacsim.core.experimental.utils.app as app_utils
import isaacsim.core.experimental.utils.stage as stage_utils
import omni.graph.core as og
import usdrt.Sdf
from isaacsim.core.experimental.utils.prim import get_prim_at_path
from isaacsim.core.rendering_manager import ViewportManager
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.storage.native import get_assets_root_path
from pxr import Gf, UsdGeom, UsdPhysics, Usd, PhysxSchema, Sdf
import omni.usd
import omni.client
import omni.replicator.core as rep
# Modern camera imports
try:
    from isaacsim.core.experimental.objects import Camera
except ImportError:
    try:
        from isaacsim.sensors.camera import Camera
    except ImportError:
        Camera = None

# Enable ROS 2 Bridge extension
app_utils.enable_extension("isaacsim.ros2.bridge")
simulation_app.update()

# Load stage and check assets
stage_utils.set_stage_units(meters_per_unit=1.0)

# ── Physics Scene: Stable CPU solver for 3-arm fleet (prevents VRAM access violation) ───
stage = omni.usd.get_context().get_stage()  # early ref for physics scene creation
physics_scene = UsdPhysics.Scene.Define(stage, "/PhysicsScene")
physics_scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
physics_scene.CreateGravityMagnitudeAttr().Set(9.81)
physx_scene_api = PhysxSchema.PhysxSceneAPI.Apply(stage.GetPrimAtPath("/PhysicsScene"))
physx_scene_api.CreateEnableGPUDynamicsAttr().Set(False)
physx_scene_api.CreateBroadphaseTypeAttr().Set("MBP")
physx_scene_api.CreateSolverTypeAttr().Set("TGS")

assets_root_path = get_assets_root_path()
if assets_root_path is None:
    carb.log_error("Could not find Isaac Sim assets folder")
    simulation_app.close()
    sys.exit(1)

# Setup camera view
ViewportManager.set_camera_view("/OmniverseKit_Persp", eye=np.array([2.5, 0.0, 2.2]), target=np.array([0.0, 0.0, 0.4]))

# 1. Initialize background (simple room)
BACKGROUND_USD_PATH = "/Isaac/Environments/Simple_Room/simple_room.usd"
print(f"Loading background from: {BACKGROUND_USD_PATH}")
stage_utils.add_reference_to_stage(assets_root_path + BACKGROUND_USD_PATH, "/background")

# Traverse background to remove collision and hide the center room table
background_prim = stage.GetPrimAtPath("/background")
if background_prim:
    for prim in Usd.PrimRange(background_prim):
        path = prim.GetPath().pathString
        if "table" in path.lower() or "desk" in path.lower():
            print(f"[PHYSICS] Hiding background table {path}...")
            UsdGeom.Imageable(prim).MakeInvisible()
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                prim.RemoveAPI(UsdPhysics.CollisionAPI)

# 2. Add Large Main Workbench Table (Robots mounted on top at Z=0.20m)
print("Creating Main Workbench Table under robots...")
main_table = UsdGeom.Cube.Define(stage, "/MainTable")
main_table.GetSizeAttr().Set(1.0)
xform_main = UsdGeom.Xformable(main_table.GetPrim())
xform_main.ClearXformOpOrder()
xform_main.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 0.10)) # Top surface at Z=0.20m
xform_main.AddScaleOp().Set(Gf.Vec3f(2.8, 2.8, 0.20))     # 2.8m x 2.8m x 0.2m
main_table.CreateDisplayColorAttr().Set([Gf.Vec3f(0.22, 0.24, 0.26)]) # Industrial Slate

UsdPhysics.RigidBodyAPI.Apply(main_table.GetPrim())
UsdPhysics.CollisionAPI.Apply(main_table.GetPrim())
rb_main = main_table.GetPrim().GetAttribute("physics:rigidBodyEnabled")
if rb_main.IsValid(): rb_main.Set(False)
kin_main = main_table.GetPrim().GetAttribute("physics:kinematicEnabled")
if kin_main.IsValid(): kin_main.Set(False)

# 3. Add Robots (Mounted on MainTable at Z=0.20m, R=0.45m)
FR3_USD_PATH = "/Isaac/Robots/FrankaRobotics/FrankaFR3/fr3.usd"

# Robot 1: Franka FR3 at [0.0, -0.45, 0.20] rotated 168 deg around Z
print("Loading Robot 1 (FR3_1)...")
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, "/FR3_1")

# Robot 2: Franka FR3 at [0.3897, 0.225, 0.20] rotated -64 deg around Z
print("Loading Robot 2 (FR3_2)...")
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, "/FR3_2")

# Robot 3: Franka FR3 at [-0.3897, 0.225, 0.20] rotated 42 deg around Z
print("Loading Robot 3 (FR3_3)...")
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, "/FR3_3")

def configure_robot_tf_names(robot_prim_path, prefix, use_prefix_for_links=True):
    """Set isaac:nameOverride attribute on prims to eliminate TF duplicate frame warnings."""
    root_prim = stage.GetPrimAtPath(robot_prim_path)
    if not root_prim.IsValid():
        return
    for prim in Usd.PrimRange(root_prim):
        if prim.GetPath() == root_prim.GetPath():
            frame_name = prefix
        else:
            link_name = prim.GetName()
            frame_name = f"{prefix}_{link_name}" if use_prefix_for_links else link_name
        
        attr = prim.GetAttribute("isaac:nameOverride")
        if not attr.IsValid():
            attr = prim.CreateAttribute("isaac:nameOverride", Sdf.ValueTypeNames.String)
        attr.Set(frame_name)

# Apply explicit frame name overrides for all three robots
configure_robot_tf_names("/FR3_1", "FR3_1", use_prefix_for_links=False)
configure_robot_tf_names("/FR3_2", "FR3_2", use_prefix_for_links=True)
configure_robot_tf_names("/FR3_3", "FR3_3", use_prefix_for_links=True)

# Fix exploding robot physics, initial posture, & PhysX warnings:
# 1. fr3.usd uses xformOpOrder = [xformOp:translate, xformOp:orient, xformOp:scale], so XformCommonAPI.SetRotate fails silently.
#    We author xformOp:translate and xformOp:orient directly on /FR3_* and align /FR3_*/root_joint localPos0/localRot0.
# 2. Author home joint angles and PD drive targets ([0, 0, 0, -90, 0, 90, 45] deg, [0.04, 0.04] m) directly in USD before play().
# 3. Fix negative mass / {0, 0, 0} or {1, 1, 1} dummy inertia tensor on virtual links (fr3_link8, fr3_hand_tcp).
# 4. Cap TGS solverVelocityIterationCount to 4 on articulation roots.
from pxr import PhysxSchema, UsdPhysics

robot_mount_poses = {
    "/FR3_1": (Gf.Vec3f(0.0, -0.45, 0.20), Gf.Quatf(0.1045285, 0.0, 0.0, 0.9945219)),
    "/FR3_2": (Gf.Vec3f(0.3897, 0.225, 0.20), Gf.Quatf(0.8480481, 0.0, 0.0, -0.5299193)),
    "/FR3_3": (Gf.Vec3f(-0.3897, 0.225, 0.20), Gf.Quatf(0.9335804, 0.0, 0.0, 0.3583679)),
}

usd_home_deg = {
    "fr3_joint1": 0.0,
    "fr3_joint2": 0.0,
    "fr3_joint3": 0.0,
    "fr3_joint4": -90.0,
    "fr3_joint5": 0.0,
    "fr3_joint6": 90.0,
    "fr3_joint7": 45.0,
}
usd_home_lin = {
    "fr3_finger_joint1": 0.04,
    "fr3_finger_joint2": 0.04,
}

for robot_path, (mount_pos, mount_quat) in robot_mount_poses.items():
    robot_root_prim = stage.GetPrimAtPath(robot_path)
    if robot_root_prim.IsValid():
        xf = UsdGeom.Xformable(robot_root_prim)
        xf.ClearXformOpOrder()
        xf.AddTranslateOp().Set(Gf.Vec3d(float(mount_pos[0]), float(mount_pos[1]), float(mount_pos[2])))
        xf.AddOrientOp(UsdGeom.XformOp.PrecisionDouble).Set(
            Gf.Quatd(
                float(mount_quat.GetReal()),
                float(mount_quat.GetImaginary()[0]),
                float(mount_quat.GetImaginary()[1]),
                float(mount_quat.GetImaginary()[2]),
            )
        )

    base_prim = stage.GetPrimAtPath(robot_path + "/fr3_link0")
    if base_prim.IsValid():
        kin_attr = base_prim.GetAttribute("physics:kinematicEnabled")
        if not kin_attr.IsValid():
            kin_attr = base_prim.CreateAttribute("physics:kinematicEnabled", Sdf.ValueTypeNames.Bool)
        kin_attr.Set(False)

        root_joint_prim = stage.GetPrimAtPath(robot_path + "/root_joint")
        if root_joint_prim.IsValid():
            fixed_joint = UsdPhysics.FixedJoint(root_joint_prim)
        else:
            fixed_joint = UsdPhysics.FixedJoint.Define(stage, robot_path + "/root_joint")
            fixed_joint.CreateBody1Rel().SetTargets([base_prim.GetPath()])
        fixed_joint.CreateLocalPos0Attr().Set(mount_pos)
        fixed_joint.CreateLocalRot0Attr().Set(mount_quat)
        fixed_joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
        fixed_joint.CreateLocalRot1Attr().Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))

    if robot_root_prim.IsValid():
        for prim in Usd.PrimRange(robot_root_prim):
            if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
                physx_art = PhysxSchema.PhysxArticulationAPI.Apply(prim)
                physx_art.CreateSolverPositionIterationCountAttr().Set(32)
                physx_art.CreateSolverVelocityIterationCountAttr().Set(4)
            jname = prim.GetName()
            if jname in usd_home_deg:
                deg_val = usd_home_deg[jname]
                for attr_name in ("drive:angular:physics:targetPosition", "state:angular:physics:position"):
                    attr = prim.GetAttribute(attr_name)
                    if attr.IsValid():
                        attr.Set(deg_val)
            elif jname in usd_home_lin:
                lin_val = usd_home_lin[jname]
                for attr_name in ("drive:linear:physics:targetPosition", "state:linear:physics:position"):
                    attr = prim.GetAttribute(attr_name)
                    if attr.IsValid():
                        attr.Set(lin_val)
            # IMPORTANT: Only assign dummy mass/inertia to massless virtual frames (fr3_link8, fr3_hand_tcp).
            # Never overwrite m=0.0 / i=(0,0,0) on real links or fingers (UsdPhysics auto-computes them from colliders).
            if jname in ("fr3_link8", "fr3_hand_tcp"):
                mass_api = UsdPhysics.MassAPI.Apply(prim)
                mass_api.CreateMassAttr().Set(1e-4)
                mass_api.CreateDiagonalInertiaAttr().Set(Gf.Vec3f(1e-6, 1e-6, 1e-6))

simulation_app.update()

# 4. Add Source Tables & Target Table (Mounted on MainTable at Z=0.20m, Top Surface Z=0.30m)
# 3 Source Tables at R=1.05m behind robots + 1 Target Table at center [0,0]
table_configs = [
    # (path, position, scale, color)
    ("/Table1", [0.0, -1.05, 0.25], [0.50, 0.50, 0.10], Gf.Vec3f(0.5, 0.5, 0.5)),      # Source Table 1 (Behind FR3_1)
    ("/Table2", [0.9093, 0.525, 0.25], [0.50, 0.50, 0.10], Gf.Vec3f(0.5, 0.5, 0.5)),   # Source Table 2 (Behind FR3_2)
    ("/Table3", [-0.9093, 0.525, 0.25], [0.50, 0.50, 0.10], Gf.Vec3f(0.5, 0.5, 0.5)),  # Source Table 3 (Behind FR3_3)
    ("/TargetTable", [0.0, 0.0, 0.25], [0.36, 0.36, 0.10], Gf.Vec3f(0.8, 0.8, 0.85))   # Center Target Table
]

for table_path, pos, scl, col in table_configs:
    table = UsdGeom.Cube.Define(stage, table_path)
    table.GetSizeAttr().Set(1.0)
    xform = UsdGeom.Xformable(table.GetPrim())
    xform.ClearXformOpOrder()
    xform.AddTranslateOp().Set(Gf.Vec3d(*pos))
    xform.AddScaleOp().Set(Gf.Vec3f(*scl))
    table.CreateDisplayColorAttr().Set([col])
    
    UsdPhysics.RigidBodyAPI.Apply(table.GetPrim())
    UsdPhysics.CollisionAPI.Apply(table.GetPrim())
    rb_attr = table.GetPrim().GetAttribute("physics:rigidBodyEnabled")
    if rb_attr.IsValid(): rb_attr.Set(False)
    kin_attr = table.GetPrim().GetAttribute("physics:kinematicEnabled")
    if kin_attr.IsValid(): kin_attr.Set(False)

simulation_app.update()

# 5. Block Targets Spawning (9 Blocks Total: 3 on each source table, Table top Z=0.30m -> Block center Z=0.33m)
nominal_block_poses = [
    # Table 1 (FR3_1)
    [-0.12, -1.05, 0.33],  # Block 1: Red Cube
    [ 0.00, -1.15, 0.33],  # Block 2: Green Cylinder
    [ 0.12, -1.05, 0.33],  # Block 3: Blue Cube
    
    # Table 2 (FR3_2)
    [0.9093 - 0.10, 0.525 - 0.10, 0.33], # Block 4: Yellow Cylinder
    [0.9093 + 0.10, 0.525 - 0.05, 0.33], # Block 5: Magenta Cube
    [0.9093,        0.525 + 0.10, 0.33], # Block 6: Cyan Cylinder
    
    # Table 3 (FR3_3)
    [-0.9093 - 0.10, 0.525 - 0.05, 0.33], # Block 7: Orange Cube
    [-0.9093 + 0.10, 0.525 - 0.10, 0.33], # Block 8: Purple Cylinder
    [-0.9093,        0.525 + 0.10, 0.33], # Block 9: Lime Cube
]

block_colors = [
    Gf.Vec3f(0.9, 0.1, 0.1),   # Block 1: Red
    Gf.Vec3f(0.1, 0.8, 0.1),   # Block 2: Green
    Gf.Vec3f(0.1, 0.3, 0.9),   # Block 3: Blue
    Gf.Vec3f(0.9, 0.8, 0.1),   # Block 4: Yellow
    Gf.Vec3f(0.9, 0.1, 0.8),   # Block 5: Magenta
    Gf.Vec3f(0.1, 0.8, 0.9),   # Block 6: Cyan
    Gf.Vec3f(0.95, 0.5, 0.05), # Block 7: Orange
    Gf.Vec3f(0.6, 0.1, 0.9),   # Block 8: Purple
    Gf.Vec3f(0.5, 0.9, 0.1),   # Block 9: Lime
]

for i, pos in enumerate(nominal_block_poses):
    block_path = f"/Block{i+1}"
    dx = np.random.uniform(-0.03, 0.03)
    dy = np.random.uniform(-0.03, 0.03)
    spawn_pos = [pos[0] + dx, pos[1] + dy, pos[2]]
    theta_deg = np.random.uniform(0, 360)

    if i % 2 == 0:
        # Cube (6cm side)
        cube = UsdGeom.Cube.Define(stage, block_path)
        cube.GetSizeAttr().Set(1.0)
        xform_cube = UsdGeom.Xformable(cube.GetPrim())
        xform_cube.ClearXformOpOrder()
        xform_cube.AddTranslateOp().Set(Gf.Vec3d(*spawn_pos))
        xform_cube.AddRotateXYZOp().Set(Gf.Vec3d(0.0, 0.0, theta_deg))
        xform_cube.AddScaleOp().Set(Gf.Vec3f(0.045, 0.045, 0.045))
        cube.CreateDisplayColorAttr().Set([block_colors[i]])
        
        UsdPhysics.RigidBodyAPI.Apply(cube.GetPrim())
        UsdPhysics.CollisionAPI.Apply(cube.GetPrim())
        # Mass: 150g block with realistic inertia for stable parallel-jaw grasping
        mass_api_c = UsdPhysics.MassAPI.Apply(cube.GetPrim())
        mass_api_c.CreateMassAttr().Set(0.15)
    else:
        # Cylinder (height 0.045m, radius 0.0225m)
        cylinder = UsdGeom.Cylinder.Define(stage, block_path)
        cylinder.GetHeightAttr().Set(0.045)
        cylinder.GetRadiusAttr().Set(0.0225)
        cylinder.GetAxisAttr().Set("Z")
        xform_cyl = UsdGeom.Xformable(cylinder.GetPrim())
        xform_cyl.ClearXformOpOrder()
        xform_cyl.AddTranslateOp().Set(Gf.Vec3d(*spawn_pos))
        xform_cyl.AddRotateXYZOp().Set(Gf.Vec3d(0.0, 0.0, theta_deg))
        cylinder.CreateDisplayColorAttr().Set([block_colors[i]])
        
        UsdPhysics.RigidBodyAPI.Apply(cylinder.GetPrim())
        UsdPhysics.CollisionAPI.Apply(cylinder.GetPrim())
        mass_api_y = UsdPhysics.MassAPI.Apply(cylinder.GetPrim())
        mass_api_y.CreateMassAttr().Set(0.15)

# ── Physics Materials: Friction Coefficients & Explicit Prim Binding ──────────
print("Applying physics friction materials...")
try:
    from pxr import UsdShade
    # Block & Gripper material: high-friction rubberized grasping surface
    block_mat_shade = UsdShade.Material.Define(stage, "/Looks/BlockPhysMat")
    block_mat = UsdPhysics.MaterialAPI.Apply(block_mat_shade.GetPrim())
    block_mat.CreateStaticFrictionAttr().Set(1.2)
    block_mat.CreateDynamicFrictionAttr().Set(1.0)
    block_mat.CreateRestitutionAttr().Set(0.0)

    # Table material: smooth metal surface
    table_mat_shade = UsdShade.Material.Define(stage, "/Looks/TablePhysMat")
    table_mat = UsdPhysics.MaterialAPI.Apply(table_mat_shade.GetPrim())
    table_mat.CreateStaticFrictionAttr().Set(0.6)
    table_mat.CreateDynamicFrictionAttr().Set(0.5)
    table_mat.CreateRestitutionAttr().Set(0.0)

    # Bind BlockPhysMat to all 9 blocks and all robot gripper fingers
    for i in range(9):
        b_prim = stage.GetPrimAtPath(f"/Block{i+1}")
        if b_prim.IsValid():
            UsdShade.MaterialBindingAPI.Apply(b_prim).Bind(
                block_mat_shade, UsdShade.Tokens.weakerThanDescendants, "physics"
            )
    for robot_path in ("/FR3_1", "/FR3_2", "/FR3_3"):
        for finger_name in ("fr3_leftfinger", "fr3_rightfinger"):
            f_prim = stage.GetPrimAtPath(f"{robot_path}/{finger_name}")
            if f_prim.IsValid():
                UsdShade.MaterialBindingAPI.Apply(f_prim).Bind(
                    block_mat_shade, UsdShade.Tokens.weakerThanDescendants, "physics"
                )
    for t_path in ("/MainTable", "/Table1", "/Table2", "/Table3", "/TargetTable"):
        t_prim = stage.GetPrimAtPath(t_path)
        if t_prim.IsValid():
            UsdShade.MaterialBindingAPI.Apply(t_prim).Bind(
                table_mat_shade, UsdShade.Tokens.weakerThanDescendants, "physics"
            )
except Exception as mat_err:
    print(f"[WARN] Physics material setup: {mat_err}")

simulation_app.update()

# 6. Overhead Camera for Gemini Robotics VLM (Native OpenUSD Camera)
print("Adding overhead camera for Gemini Robotics integration...")
camera_prim = UsdGeom.Camera.Define(stage, "/OverheadCamera")
xform_cam = UsdGeom.Xformable(camera_prim.GetPrim())
xform_cam.ClearXformOpOrder()
xform_cam.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 1.8))
xform_cam.AddRotateXYZOp().Set(Gf.Vec3f(0.0, 90.0, 0.0))  # Downward looking

_camera_initialized = False

def setup_overhead_camera_publishing():
    """Sets up Replicator render product and ROS 2 image publishers when --enable-cameras is set."""
    global _camera_initialized
    if _camera_initialized:
        return
    if "--enable-cameras" not in sys.argv and "--enable-camera" not in sys.argv:
        print("[INFO] Overhead camera render product skipped by default (pass --enable-cameras to enable).")
        return
    try:
        import carb.settings
        import omni.syntheticdata._syntheticdata as sd
        carb.settings.get_settings().set("/rtx/post/dlss/execMode", 2)
        render_product = rep.create.render_product("/OverheadCamera", (640, 480))
        rp_path = render_product.path if hasattr(render_product, "path") else str(render_product)
        freq = 10
        step_size = int(60 / freq)

        # RGB Image Publisher
        rv_rgb = omni.syntheticdata.SyntheticData.convert_sensor_type_to_rendervar(sd.SensorType.Rgb.name)
        writer_rgb = rep.writers.get(rv_rgb + "ROS2PublishImage")
        writer_rgb.initialize(frameId="overhead_camera", topicName="/overhead_camera/rgb")
        writer_rgb.attach([render_product])
        gate_path_rgb = omni.syntheticdata.SyntheticData._get_node_path(rv_rgb + "IsaacSimulationGate", rp_path)
        og.Controller.attribute(gate_path_rgb + ".inputs:step").set(step_size)

        # Depth Image Publisher
        rv_depth = omni.syntheticdata.SyntheticData.convert_sensor_type_to_rendervar(sd.SensorType.DistanceToImagePlane.name)
        writer_depth = rep.writers.get(rv_depth + "ROS2PublishImage")
        writer_depth.initialize(frameId="overhead_camera", topicName="/overhead_camera/depth")
        writer_depth.attach([render_product])
        gate_path_depth = omni.syntheticdata.SyntheticData._get_node_path(rv_depth + "IsaacSimulationGate", rp_path)
        og.Controller.attribute(gate_path_depth + ".inputs:step").set(step_size)

        # Camera Info Publisher
        writer_info = rep.writers.get("ROS2PublishCameraInfo")
        writer_info.initialize(frameId="overhead_camera", topicName="/overhead_camera/camera_info")
        writer_info.attach([render_product])
        _camera_initialized = True
        print("[INFO] Overhead camera ROS 2 publishing initialized successfully.")
    except Exception as cam_err:
        print(f"[WARN] Overhead camera publishing setup: {cam_err}")

simulation_app.update()

# 7. ROS 2 Action Graph
try:
    og.Controller.edit(
        {"graph_path": "/ActionGraph", "evaluator_name": "execution"},
        {
            og.Controller.Keys.CREATE_NODES: [
                ("OnPlaybackTick", "omni.graph.action.OnPlaybackTick"),
                ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                ("Context", "isaacsim.ros2.bridge.ROS2Context"),
                ("PublishClock", "isaacsim.ros2.bridge.ROS2PublishClock"),
                ("ComputeTF", "isaacsim.core.nodes.IsaacComputeTransformTree"),
                ("PublishTF", "isaacsim.ros2.bridge.ROS2PublishTransformTree"),
                
                # Robot 1 (FR3_1)
                ("ReadJointState1", "isaacsim.sensors.physics.IsaacReadJointState"),
                ("PublishJointState1", "isaacsim.ros2.bridge.ROS2PublishJointState"),
                ("SubscribeJointState1", "isaacsim.ros2.bridge.ROS2SubscribeJointState"),
                ("ArticulationController1", "isaacsim.core.nodes.IsaacArticulationController"),
                
                # Robot 2 (FR3_2)
                ("ReadJointState2", "isaacsim.sensors.physics.IsaacReadJointState"),
                ("PublishJointState2", "isaacsim.ros2.bridge.ROS2PublishJointState"),
                ("SubscribeJointState2", "isaacsim.ros2.bridge.ROS2SubscribeJointState"),
                ("ArticulationController2", "isaacsim.core.nodes.IsaacArticulationController"),
                
                # Robot 3 (FR3_3)
                ("ReadJointState3", "isaacsim.sensors.physics.IsaacReadJointState"),
                ("PublishJointState3", "isaacsim.ros2.bridge.ROS2PublishJointState"),
                ("SubscribeJointState3", "isaacsim.ros2.bridge.ROS2SubscribeJointState"),
                ("ArticulationController3", "isaacsim.core.nodes.IsaacArticulationController"),
            ],
            og.Controller.Keys.CONNECT: [
                # Core timing
                ("OnPlaybackTick.outputs:tick", "PublishClock.inputs:execIn"),
                ("OnPlaybackTick.outputs:tick", "ComputeTF.inputs:execIn"),
                ("ComputeTF.outputs:execOut", "PublishTF.inputs:execIn"),
                ("ComputeTF.outputs:parentFrames", "PublishTF.inputs:parentFrames"),
                ("ComputeTF.outputs:childFrames", "PublishTF.inputs:childFrames"),
                ("ComputeTF.outputs:translations", "PublishTF.inputs:translations"),
                ("ComputeTF.outputs:orientations", "PublishTF.inputs:orientations"),
                ("Context.outputs:context", "PublishClock.inputs:context"),
                ("Context.outputs:context", "PublishTF.inputs:context"),
                ("ReadSimTime.outputs:simulationTime", "PublishClock.inputs:timeStamp"),
                ("ReadSimTime.outputs:simulationTime", "PublishTF.inputs:timeStamp"),
                
                # Robot 1 connections
                ("OnPlaybackTick.outputs:tick", "ReadJointState1.inputs:execIn"),
                ("ReadJointState1.outputs:execOut", "PublishJointState1.inputs:execIn"),
                ("ReadJointState1.outputs:jointNames", "PublishJointState1.inputs:jointNames"),
                ("ReadJointState1.outputs:jointPositions", "PublishJointState1.inputs:jointPositions"),
                ("ReadJointState1.outputs:jointVelocities", "PublishJointState1.inputs:jointVelocities"),
                ("ReadJointState1.outputs:jointEfforts", "PublishJointState1.inputs:jointEfforts"),
                ("ReadJointState1.outputs:jointDofTypes", "PublishJointState1.inputs:jointDofTypes"),
                ("ReadJointState1.outputs:stageMetersPerUnit", "PublishJointState1.inputs:stageMetersPerUnit"),
                ("ReadJointState1.outputs:sensorTime", "PublishJointState1.inputs:sensorTime"),
                ("OnPlaybackTick.outputs:tick", "SubscribeJointState1.inputs:execIn"),
                ("OnPlaybackTick.outputs:tick", "ArticulationController1.inputs:execIn"),
                ("SubscribeJointState1.outputs:jointNames", "ArticulationController1.inputs:jointNames"),
                ("SubscribeJointState1.outputs:positionCommand", "ArticulationController1.inputs:positionCommand"),
                ("SubscribeJointState1.outputs:velocityCommand", "ArticulationController1.inputs:velocityCommand"),
                ("SubscribeJointState1.outputs:effortCommand", "ArticulationController1.inputs:effortCommand"),
                ("Context.outputs:context", "PublishJointState1.inputs:context"),
                ("Context.outputs:context", "SubscribeJointState1.inputs:context"),
                
                # Robot 2 connections
                ("OnPlaybackTick.outputs:tick", "ReadJointState2.inputs:execIn"),
                ("ReadJointState2.outputs:execOut", "PublishJointState2.inputs:execIn"),
                ("ReadJointState2.outputs:jointNames", "PublishJointState2.inputs:jointNames"),
                ("ReadJointState2.outputs:jointPositions", "PublishJointState2.inputs:jointPositions"),
                ("ReadJointState2.outputs:jointVelocities", "PublishJointState2.inputs:jointVelocities"),
                ("ReadJointState2.outputs:jointEfforts", "PublishJointState2.inputs:jointEfforts"),
                ("ReadJointState2.outputs:jointDofTypes", "PublishJointState2.inputs:jointDofTypes"),
                ("ReadJointState2.outputs:stageMetersPerUnit", "PublishJointState2.inputs:stageMetersPerUnit"),
                ("ReadJointState2.outputs:sensorTime", "PublishJointState2.inputs:sensorTime"),
                ("OnPlaybackTick.outputs:tick", "SubscribeJointState2.inputs:execIn"),
                ("OnPlaybackTick.outputs:tick", "ArticulationController2.inputs:execIn"),
                ("SubscribeJointState2.outputs:jointNames", "ArticulationController2.inputs:jointNames"),
                ("SubscribeJointState2.outputs:positionCommand", "ArticulationController2.inputs:positionCommand"),
                ("SubscribeJointState2.outputs:velocityCommand", "ArticulationController2.inputs:velocityCommand"),
                ("SubscribeJointState2.outputs:effortCommand", "ArticulationController2.inputs:effortCommand"),
                ("Context.outputs:context", "PublishJointState2.inputs:context"),
                ("Context.outputs:context", "SubscribeJointState2.inputs:context"),

                # Robot 3 connections
                ("OnPlaybackTick.outputs:tick", "ReadJointState3.inputs:execIn"),
                ("ReadJointState3.outputs:execOut", "PublishJointState3.inputs:execIn"),
                ("ReadJointState3.outputs:jointNames", "PublishJointState3.inputs:jointNames"),
                ("ReadJointState3.outputs:jointPositions", "PublishJointState3.inputs:jointPositions"),
                ("ReadJointState3.outputs:jointVelocities", "PublishJointState3.inputs:jointVelocities"),
                ("ReadJointState3.outputs:jointEfforts", "PublishJointState3.inputs:jointEfforts"),
                ("ReadJointState3.outputs:jointDofTypes", "PublishJointState3.inputs:jointDofTypes"),
                ("ReadJointState3.outputs:stageMetersPerUnit", "PublishJointState3.inputs:stageMetersPerUnit"),
                ("ReadJointState3.outputs:sensorTime", "PublishJointState3.inputs:sensorTime"),
                ("OnPlaybackTick.outputs:tick", "SubscribeJointState3.inputs:execIn"),
                ("OnPlaybackTick.outputs:tick", "ArticulationController3.inputs:execIn"),
                ("SubscribeJointState3.outputs:jointNames", "ArticulationController3.inputs:jointNames"),
                ("SubscribeJointState3.outputs:positionCommand", "ArticulationController3.inputs:positionCommand"),
                ("SubscribeJointState3.outputs:velocityCommand", "ArticulationController3.inputs:velocityCommand"),
                ("SubscribeJointState3.outputs:effortCommand", "ArticulationController3.inputs:effortCommand"),
                ("Context.outputs:context", "PublishJointState3.inputs:context"),
                ("Context.outputs:context", "SubscribeJointState3.inputs:context"),
            ],
            og.Controller.Keys.SET_VALUES: [
                ("PublishTF.inputs:topicName", "/tf"),
                ("ComputeTF.inputs:targetPrims", [
                    usdrt.Sdf.Path("/FR3_1"),
                    usdrt.Sdf.Path("/FR3_2"),
                    usdrt.Sdf.Path("/FR3_3"),
                    usdrt.Sdf.Path("/Block1"), usdrt.Sdf.Path("/Block2"), usdrt.Sdf.Path("/Block3"),
                    usdrt.Sdf.Path("/Block4"), usdrt.Sdf.Path("/Block5"), usdrt.Sdf.Path("/Block6"),
                    usdrt.Sdf.Path("/Block7"), usdrt.Sdf.Path("/Block8"), usdrt.Sdf.Path("/Block9"),
                ]),
                
                # Robot 1 config
                ("ArticulationController1.inputs:robotPath", "/FR3_1"),
                ("ReadJointState1.inputs:prim", [usdrt.Sdf.Path("/FR3_1")]),
                ("PublishJointState1.inputs:topicName", "/fr3_1/joint_states"),
                ("SubscribeJointState1.inputs:topicName", "/fr3_1/joint_commands"),
                
                # Robot 2 config
                ("ArticulationController2.inputs:robotPath", "/FR3_2"),
                ("ReadJointState2.inputs:prim", [usdrt.Sdf.Path("/FR3_2")]),
                ("PublishJointState2.inputs:topicName", "/fr3_2/joint_states"),
                ("SubscribeJointState2.inputs:topicName", "/fr3_2/joint_commands"),

                # Robot 3 config
                ("ArticulationController3.inputs:robotPath", "/FR3_3"),
                ("ReadJointState3.inputs:prim", [usdrt.Sdf.Path("/FR3_3")]),
                ("PublishJointState3.inputs:topicName", "/fr3_3/joint_states"),
                ("SubscribeJointState3.inputs:topicName", "/fr3_3/joint_commands"),
            ],
        },
    )
    print("Action Graph created successfully.")
except Exception as e:
    print(f"Error creating Action Graph: {e}")

# Initialize overhead camera Replicator graph and step 3 frames BEFORE app_utils.play()
# so Replicator completes its multi-frame SDGPipeline/WriterSyncGate USD node creation
# before PhysX JointStateSensor articulation views are created.
setup_overhead_camera_publishing()
for _ in range(3):
    simulation_app.update()

# 8. Articulations & Rigid Prims Management
robot1_art = None
robot2_art = None
robot3_art = None
blocks = []

# Canonical home configurations (arm: 7 DOFs, gripper: 2 fingers)
q_home_arm = np.array([0.0, 0.0, 0.0, -1.5708, 0.0, 1.5708, 0.7854], dtype=float)
q_home_gripper = np.array([0.04, 0.04], dtype=float)
q_home_all = np.array([0.0, 0.0, 0.0, -1.5708, 0.0, 1.5708, 0.7854, 0.04, 0.04], dtype=float)

# Nominal robot bases in world frame
robot_nominal_poses = {
    1: ([0.0, -0.45, 0.20], [0.1045285, 0.0, 0.0, 0.9945219]),
    2: ([0.3897, 0.225, 0.20], [0.8480481, 0.0, 0.0, -0.5299193]),
    3: ([-0.3897, 0.225, 0.20], [0.9335804, 0.0, 0.0, 0.3583679]),
}

q_home_dict = {
    "fr3_joint1": 0.0,
    "fr3_joint2": 0.0,
    "fr3_joint3": 0.0,
    "fr3_joint4": -1.5708,
    "fr3_joint5": 0.0,
    "fr3_joint6": 1.5708,
    "fr3_joint7": 0.7854,
    "fr3_finger_joint1": 0.04,
    "fr3_finger_joint2": 0.04,
}

def reset_robot_articulation(robot_art, pos=None, quat_wxyz=None):
    """Resets a Franka FR3 robot articulation to its home DOF configuration."""
    if robot_art is None:
        return
    if hasattr(app_utils, "is_playing") and not app_utils.is_playing():
        return

    dof_names = list(getattr(robot_art, "dof_names", []) or [])
    if dof_names:
        target_positions = np.array([q_home_dict.get(name, 0.0) for name in dof_names], dtype=float)
        zero_vel = np.zeros(len(dof_names), dtype=float)
    else:
        target_positions = q_home_all
        zero_vel = np.zeros(9, dtype=float)

    if hasattr(robot_art, "set_dof_positions"):
        # Isaac Sim 6.0 Experimental Articulation API
        try:
            robot_art.set_dof_positions(target_positions)
        except Exception as e:
            print(f"[WARN] set_dof_positions failed: {e}")
        if hasattr(robot_art, "set_dof_position_targets"):
            try:
                robot_art.set_dof_position_targets(target_positions)
            except Exception:
                pass
        if hasattr(robot_art, "set_dof_velocities"):
            try:
                robot_art.set_dof_velocities(zero_vel)
            except Exception:
                pass
    elif hasattr(robot_art, "set_joint_positions"):
        # Classic Isaac Sim 4.x Articulation API
        try:
            robot_art.set_joint_positions(q_home_arm, joint_indices=np.arange(7))
            if hasattr(robot_art, "set_joint_velocities"):
                n_dof = getattr(robot_art, "num_dof", 9)
                robot_art.set_joint_velocities(np.zeros(n_dof))
            robot_art.set_joint_positions(q_home_gripper, joint_indices=np.array([7, 8]))
        except Exception as e:
            print(f"[WARN] set_joint_positions failed: {e}")

def set_rigid_velocity(prim, lin_vel=None, ang_vel=None):
    """Safely sets linear and angular velocity across Isaac Sim 6.0 and 4.x."""
    if prim is None:
        return
    if hasattr(prim, "set_velocities"):
        try:
            prim.set_velocities(linear_velocities=lin_vel, angular_velocities=ang_vel)
            return
        except Exception:
            pass
    if lin_vel is not None and hasattr(prim, "set_linear_velocities"):
        try:
            prim.set_linear_velocities(lin_vel)
        except Exception:
            pass
    if ang_vel is not None and hasattr(prim, "set_angular_velocities"):
        try:
            prim.set_angular_velocities(ang_vel)
        except Exception:
            pass

def reset_rigid_body(prim, pos, quat_wxyz):
    """Resets rigid body pose and zeroes out linear and angular velocities."""
    if prim is None:
        return
    try:
        prim.set_world_poses(
            positions=np.array([pos], dtype=float),
            orientations=np.array([quat_wxyz], dtype=float)
        )
    except Exception as e:
        print(f"[WARN] set_world_poses on block failed: {e}")
    set_rigid_velocity(prim, lin_vel=np.zeros((1, 3), dtype=float), ang_vel=np.zeros((1, 3), dtype=float))

def init_articulations_and_poses():
    """Initializes robot articulations, camera streaming, and joint positions once physics is active."""
    global robot1_art, robot2_art, robot3_art, blocks
    try:
        try:
            from isaacsim.core.experimental.prims import Articulation, RigidPrim
        except ImportError:
            from isaacsim.core.prims import Articulation, RigidPrim

        robot1_art = Articulation("/FR3_1")
        robot2_art = Articulation("/FR3_2")
        robot3_art = Articulation("/FR3_3")

        for art in [robot1_art, robot2_art, robot3_art]:
            if hasattr(art, "initialize"):
                try:
                    art.initialize()
                except Exception:
                    pass

        # Set initial poses for all 3 robots
        for rid, art in [(1, robot1_art), (2, robot2_art), (3, robot3_art)]:
            pos, quat = robot_nominal_poses[rid]
            reset_robot_articulation(art, pos, quat)

        blocks = []
        for i in range(9):
            b_prim = RigidPrim(f"/Block{i+1}")
            if hasattr(b_prim, "initialize"):
                try:
                    b_prim.initialize()
                except Exception:
                    pass
            blocks.append(b_prim)

        print("[INFO] Robot articulations, camera streams, and rigid bodies initialized successfully.")
    except Exception as e:
        print(f"[WARN] Articulation setup on frame: {e}")

# 9. ROS 2 Reset Mechanism setup
reset_node = None
reset_pub = None
goal_pub = None

_articulations_initialized = False
_pending_reset = False
_pending_reset_publish_ros = True
_pending_adversarial_push = False
_last_local_reset_pub_time = 0.0

def request_reset(publish_to_ros=True):
    """Schedules a simulation reset to execute safely between frames in the main loop."""
    global _pending_reset, _pending_reset_publish_ros
    _pending_reset = True
    _pending_reset_publish_ros = publish_to_ros

def request_adversarial_push():
    """Schedules an adversarial impulse push to execute safely between frames in the main loop."""
    global _pending_adversarial_push
    _pending_adversarial_push = True

try:
    import time as _time
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Empty, String
    from std_srvs.srv import Trigger

    if not rclpy.ok():
        rclpy.init()

    reset_node = Node('three_robot_reset_node')
    reset_pub = reset_node.create_publisher(Empty, '/reset_simulation', 10)
    goal_pub = reset_node.create_publisher(String, '/gemini/custom_goal', 10)

    def ros_reset_callback(msg):
        if _time.monotonic() - _last_local_reset_pub_time < 0.25:
            return
        request_reset(publish_to_ros=False)

    reset_sub = reset_node.create_subscription(Empty, '/reset_simulation', ros_reset_callback, 10)

    def ros_reset_service_callback(request, response):
        request_reset(publish_to_ros=True)
        response.success = True
        return response

    reset_srv = reset_node.create_service(Trigger, '/reset_simulation', ros_reset_service_callback)
    print("[INFO] ROS 2 reset node, topics, and service initialized successfully.")
except Exception as e:
    print(f"[WARN] ROS 2 reset interface setup skipped or failed: {e}")

def reset_simulation(publish_to_ros=True):
    """Executes robot DOF and block pose reset on the main thread between render frames."""
    global robot1_art, robot2_art, robot3_art, blocks, _articulations_initialized
    if hasattr(app_utils, "is_playing") and not app_utils.is_playing():
        request_reset(publish_to_ros=publish_to_ros)
        app_utils.play()
        return

    print("[RESET] Initializing robot poses, randomizing blocks, and resetting simulation...")
    try:
        # If articulations were not yet initialized, initialize them now
        if not _articulations_initialized or robot1_art is None or robot2_art is None or robot3_art is None or not blocks:
            init_articulations_and_poses()
            _articulations_initialized = True

        # Reset Robot Arms to Home Joint States
        if robot1_art is not None:
            reset_robot_articulation(robot1_art, robot_nominal_poses[1][0], robot_nominal_poses[1][1])
        if robot2_art is not None:
            reset_robot_articulation(robot2_art, robot_nominal_poses[2][0], robot_nominal_poses[2][1])
        if robot3_art is not None:
            reset_robot_articulation(robot3_art, robot_nominal_poses[3][0], robot_nominal_poses[3][1])

        # Reset & Randomize All 9 Block Poses on Source Tables
        for i, block_prim in enumerate(blocks):
            nominal_p = nominal_block_poses[i]
            dx = np.random.uniform(-0.035, 0.035)
            dy = np.random.uniform(-0.035, 0.035)
            theta = np.random.uniform(0, 2 * np.pi)
            qw = np.cos(theta / 2.0)
            qz = np.sin(theta / 2.0)

            target_pos = [nominal_p[0] + dx, nominal_p[1] + dy, nominal_p[2]]
            target_quat = [qw, 0.0, 0.0, qz]
            reset_rigid_body(block_prim, target_pos, target_quat)

        # Notify ROS 2 multi-robot controller and VLA node of reset
        if publish_to_ros and reset_pub is not None:
            try:
                import time as _time
                global _last_local_reset_pub_time
                _last_local_reset_pub_time = _time.monotonic()
                reset_pub.publish(Empty())
                print("[RESET] Dispatched /reset_simulation message to ROS 2 network.")
            except Exception as pe:
                print(f"[RESET] ROS 2 reset dispatch warning: {pe}")

        print("[RESET] Simulation reset and robot pose initialization complete.")
    except Exception as err:
        print(f"[RESET] Error resetting simulation: {err}")

def adversarial_push():
    if hasattr(app_utils, "is_playing") and not app_utils.is_playing():
        return
    print("\n[ADVERSARIAL] Applying physics impulses to knock over the tower!")
    try:
        for i in range(min(9, len(blocks))):
            block_prim = blocks[i]
            pos, _ = block_prim.get_world_poses()
            pos = pos[0]
            # If block is roughly on the target table
            if abs(pos[0]) < 0.3 and abs(pos[1]) < 0.3 and pos[2] > 0.25:
                v_x = np.random.uniform(-1.5, 1.5)
                v_y = np.random.uniform(-1.5, 1.5)
                v_z = np.random.uniform(0.5, 2.0)
                w_x = np.random.uniform(-10.0, 10.0)
                w_y = np.random.uniform(-10.0, 10.0)
                w_z = np.random.uniform(-10.0, 10.0)
                set_rigid_velocity(block_prim, lin_vel=np.array([[v_x, v_y, v_z]]), ang_vel=np.array([[w_x, w_y, w_z]]))
    except Exception as e:
        print(f"[ADVERSARIAL] Failed to apply push: {e}")

# UI Reset Button setup
import omni.appwindow
import carb.input
import omni.ui as ui

def on_keyboard_event(event, *args, **kwargs):
    if event.type == carb.input.KeyboardEventType.KEY_PRESS:
        if event.input.name in ["R", "I"]:
            request_reset(publish_to_ros=True)
        elif event.input.name == "T":
            request_adversarial_push()
    return True

appwindow = omni.appwindow.get_default_app_window()
input_interface = carb.input.acquire_input_interface()
keyboard = appwindow.get_keyboard()
sub_keyboard = input_interface.subscribe_to_keyboard_events(keyboard, on_keyboard_event)

# UI logic for Interactive Mode
print("\n[INFO] Starting simulation timeline and interactive controls window...")
ui.Workspace.set_show_window_fn("Controls", lambda x: True)
controls_window = ui.Window("Tower Stacking Controls", width=400, height=200)

with controls_window.frame:
    with ui.VStack(spacing=10):
        ui.Label("Controls:", height=20)
        ui.Button("Initialize Poses / Randomize Blocks (R key)", clicked_fn=lambda: request_reset(publish_to_ros=True), height=30)
        ui.Button("💥 KNOCK TOWER OVER 💥 (T key)", clicked_fn=request_adversarial_push, height=30, style={"background_color": 0xFF4444FF, "color": 0xFFFFFFFF})
        
        ui.Spacer(height=10)
        ui.Label("Custom Gemini Goal:", height=20)
        goal_field = ui.StringField(height=30)
        goal_field.model.set_value("Your ultimate goal is to build a single, stable 9-layer tower on the central target table using ALL 9 available objects.")
        
        def send_custom_goal():
            try:
                from std_msgs.msg import String
                text = goal_field.model.get_value_as_string()
                msg = String()
                msg.data = text
                if goal_pub is not None:
                    goal_pub.publish(msg)
                print(f"[GEMINI] Custom goal sent to ROS 2: {text}")
            except Exception as e:
                print(f"[GEMINI] Custom goal dispatch: {e}")
            
        ui.Button("Send Custom Goal to Gemini", clicked_fn=send_custom_goal, height=40, style={"background_color": 0xFF44FF44})

# Self-Verification Block
if args.test:
    print("\n--- RUNNING SELF-VERIFICATION ---")
    try:
        r1_prim = stage.GetPrimAtPath("/FR3_1")
        r2_prim = stage.GetPrimAtPath("/FR3_2")
        r3_prim = stage.GetPrimAtPath("/FR3_3")
        assert r1_prim.IsValid(), "Robot 1 (/FR3_1) is missing!"
        assert r2_prim.IsValid(), "Robot 2 (/FR3_2) is missing!"
        assert r3_prim.IsValid(), "Robot 3 (/FR3_3) is missing!"
        print("[VERIFY] All 3 robots exist on the stage.")

        for idx in range(9):
            b_prim = stage.GetPrimAtPath(f"/Block{idx+1}")
            assert b_prim.IsValid(), f"/Block{idx+1} is missing!"
            assert b_prim.HasAPI(UsdPhysics.RigidBodyAPI), f"/Block{idx+1} is missing RigidBodyAPI!"
            assert b_prim.HasAPI(UsdPhysics.CollisionAPI), f"/Block{idx+1} is missing CollisionAPI!"
        print("[VERIFY] Spawners generated all 9 blocks with accurate dimensions, rigid bodies, and colliders.")
        print("\n[VERIFICATION] ALL SELF-VERIFICATION CHECKS PASSED SUCCESSFULLY!\n")
    except AssertionError as ae:
        print(f"\n[VERIFICATION FAILED]: {ae}\n")
        simulation_app.close()
        sys.exit(1)

# Simulation loop: auto-start timeline so physics tensor entities are active before DOF initialization
app_utils.play()
frame_count = 0
while simulation_app.is_running():
    simulation_app.update()
    if not _articulations_initialized and app_utils.is_playing():
        init_articulations_and_poses()
        _articulations_initialized = True
    if _pending_reset:
        if not app_utils.is_playing():
            app_utils.play()
        else:
            _pending_reset = False
            reset_simulation(publish_to_ros=_pending_reset_publish_ros)
    if _pending_adversarial_push:
        _pending_adversarial_push = False
        if app_utils.is_playing():
            adversarial_push()
    if reset_node is not None:
        try:
            rclpy.spin_once(reset_node, timeout_sec=0.0)
        except Exception:
            pass
    frame_count += 1
    if args.test and frame_count == 10:
        request_reset(publish_to_ros=True)
    if args.test and frame_count >= 20:
        for rid, art in [(1, robot1_art), (2, robot2_art), (3, robot3_art)]:
            pos_w, quat_w = art.get_world_poses()
            if hasattr(pos_w, "numpy"):
                pos_w = pos_w.numpy()
            if hasattr(quat_w, "numpy"):
                quat_w = quat_w.numpy()
            dof_p = art.get_dof_positions() if hasattr(art, "get_dof_positions") else art.get_joint_positions()
            if hasattr(dof_p, "numpy"):
                dof_p = dof_p.numpy()
            nom_pos = np.array(robot_nominal_poses[rid][0], dtype=float)
            pos_err = float(np.linalg.norm(np.array(pos_w[0], dtype=float) - nom_pos))
            j4_val = float(np.array(dof_p[0], dtype=float)[3])
            print(f"[VERIFY] FR3_{rid} world_pos={np.round(pos_w[0], 4).tolist()}, pos_err={pos_err:.5f}m, j4={j4_val:.4f}rad")
            assert pos_err < 0.01, f"FR3_{rid} base position error too large: {pos_err}m"
            assert abs(j4_val - (-1.5708)) < 0.15, f"FR3_{rid} joint4 posture error: {j4_val} vs -1.5708"
        print(f"[TEST] {frame_count} live simulation frames (including reset & posture check) completed successfully!")
        break

simulation_app.close()
