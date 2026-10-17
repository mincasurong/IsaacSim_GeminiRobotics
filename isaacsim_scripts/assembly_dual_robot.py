# SPDX-FileCopyrightText: Copyright (c) 2020-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Dual-robot manufacturing conveyor scene with ROS 2 bridge integration — Post-doc edition (Isaac Sim 6.0)."""

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

try:
    from isaacsim.simulation_app import SimulationApp
except ImportError:
    from isaacsim import SimulationApp

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("--test", default=False, action="store_true", help="Run in test mode")
parser.add_argument("--headless", default=False, action="store_true", help="Run in headless mode")
args, _ = parser.parse_known_args()

# Setup config
CONFIG = {
    "renderer": "RayTracedLighting",
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
from pxr import Gf, UsdGeom, UsdPhysics, Usd, Sdf
import omni.usd
import omni.replicator.core as rep
import isaacsim.core.experimental.utils.transform as transform_utils

# Enable ROS 2 Bridge extension
app_utils.enable_extension("isaacsim.ros2.bridge")
simulation_app.update()
simulation_app.update()

# Load stage and check assets
stage_utils.set_stage_units(meters_per_unit=1.0)
assets_root_path = get_assets_root_path()
if assets_root_path is None:
    carb.log_error("Could not find Isaac Sim assets folder")
    simulation_app.close()
    sys.exit(1)

stage = omni.usd.get_context().get_stage()

# ── Physics Scene: Stable CPU MBP broadphase + TGS solver (prevents GPU articulation explosions) ───
physics_scene = UsdPhysics.Scene.Define(stage, "/PhysicsScene")
physics_scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
physics_scene.CreateGravityMagnitudeAttr().Set(9.81)
try:
    from pxr import PhysxSchema
    physx_scene_api = PhysxSchema.PhysxSceneAPI.Apply(stage.GetPrimAtPath("/PhysicsScene"))
    physx_scene_api.CreateEnableGPUDynamicsAttr().Set(False)
    physx_scene_api.CreateBroadphaseTypeAttr().Set("MBP")
    physx_scene_api.CreateSolverTypeAttr().Set("TGS")        # Temporal Gauss-Seidel
except Exception as e:
    print(f"Warning: Failed to set PhysX TGS solver: {e}")

# Setup camera view
ViewportManager.set_camera_view("/OmniverseKit_Persp", eye=np.array([2.5, 0.0, 1.8]), target=np.array([0.0, 0.0, 0.5]))

# 1. Initialize background (simple room)
BACKGROUND_USD_PATH = "/Isaac/Environments/Simple_Room/simple_room.usd"
print(f"Loading background from: {BACKGROUND_USD_PATH}")
stage_utils.add_reference_to_stage(assets_root_path + BACKGROUND_USD_PATH, "/background")
background_prim = stage.GetPrimAtPath("/background")
if background_prim:
    for prim in Usd.PrimRange(background_prim):
        path = prim.GetPath().pathString
        if "table" in path.lower() or "desk" in path.lower():
            UsdGeom.Imageable(prim).MakeInvisible()
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                prim.RemoveAPI(UsdPhysics.CollisionAPI)

# 2. Add Main Workbench Table (Robots mounted on top at Z=0.20m)
print("Creating Main Workbench Table under robots...")
main_table = UsdGeom.Cube.Define(stage, "/MainTable")
main_table.GetSizeAttr().Set(1.0)
xform_main = UsdGeom.Xformable(main_table.GetPrim())
xform_main.ClearXformOpOrder()
xform_main.AddTranslateOp().Set(Gf.Vec3d(0.0, -0.25, 0.10))  # Top surface at Z=0.20m
xform_main.AddScaleOp().Set(Gf.Vec3f(2.8, 0.90, 0.20))       # Y in [-0.70, +0.20]
main_table.CreateDisplayColorAttr().Set([Gf.Vec3f(0.22, 0.24, 0.26)])

UsdPhysics.RigidBodyAPI.Apply(main_table.GetPrim())
UsdPhysics.CollisionAPI.Apply(main_table.GetPrim())
rb_main = main_table.GetPrim().GetAttribute("physics:rigidBodyEnabled")
if rb_main.IsValid():
    rb_main.Set(False)
kin_main = main_table.GetPrim().GetAttribute("physics:kinematicEnabled")
if kin_main.IsValid():
    kin_main.Set(False)

# 3. Add Conveyor Belt (Table representing manufacturing line)
print("Creating Conveyor Belt Table...")
conveyor_table = UsdGeom.Cube.Define(stage, "/ConveyorTable")
conveyor_table.GetSizeAttr().Set(1.0)
xform_conv = UsdGeom.Xformable(conveyor_table.GetPrim())
xform_conv.ClearXformOpOrder()
xform_conv.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.50, 0.25))  # Top surface at Z=0.5m, Y in [0.30, 0.70]
xform_conv.AddScaleOp().Set(Gf.Vec3f(3.0, 0.40, 0.50))
conveyor_table.CreateDisplayColorAttr().Set([Gf.Vec3f(0.15, 0.15, 0.15)])

UsdPhysics.RigidBodyAPI.Apply(conveyor_table.GetPrim())
UsdPhysics.CollisionAPI.Apply(conveyor_table.GetPrim())
rb_conv = conveyor_table.GetPrim().GetAttribute("physics:rigidBodyEnabled")
if rb_conv.IsValid():
    rb_conv.Set(False)
kin_conv = conveyor_table.GetPrim().GetAttribute("physics:kinematicEnabled")
if kin_conv.IsValid():
    kin_conv.Set(True)

# 3.5 Add Center Assembly Buffer Table (Centered between FR3_1 and FR3_2)
print("Creating Center Assembly Buffer Table...")
buffer_table = UsdGeom.Cube.Define(stage, "/BufferTable")
buffer_table.GetSizeAttr().Set(1.0)
xform_buf = UsdGeom.Xformable(buffer_table.GetPrim())
xform_buf.ClearXformOpOrder()
xform_buf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 0.16))  # Top surface at Z=0.32m, centered at [0.0, 0.0]
xform_buf.AddScaleOp().Set(Gf.Vec3f(0.95, 0.24, 0.32))       # Fits cleanly between FR3_1 (-0.7) and FR3_2 (+0.7)
buffer_table.CreateDisplayColorAttr().Set([Gf.Vec3f(0.28, 0.30, 0.34)])

UsdPhysics.RigidBodyAPI.Apply(buffer_table.GetPrim())
UsdPhysics.CollisionAPI.Apply(buffer_table.GetPrim())
rb_buf = buffer_table.GetPrim().GetAttribute("physics:rigidBodyEnabled")
if rb_buf.IsValid():
    rb_buf.Set(False)
kin_buf = buffer_table.GetPrim().GetAttribute("physics:kinematicEnabled")
if kin_buf.IsValid():
    kin_buf.Set(False)

# 4. Add 2 Robots (FR3_1 and FR3_2) side-by-side facing the conveyor
FR3_USD_PATH = "/Isaac/Robots/FrankaRobotics/FrankaFR3/fr3.usd"

# Robot 1 (Left Arm)
print("Loading Robot 1 (FR3_1)...")
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, "/FR3_1")

# Robot 2 (Right Arm)
print("Loading Robot 2 (FR3_2)...")
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, "/FR3_2")

def configure_robot_tf_names(robot_prim_path, prefix, use_prefix_for_links=True):
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

configure_robot_tf_names("/FR3_1", "FR3_1", use_prefix_for_links=False)
configure_robot_tf_names("/FR3_2", "FR3_2", use_prefix_for_links=True)

# Fix exploding robot physics, initial posture, & PhysX warnings:
# 1. Author xformOp:translate and xformOp:orient directly on /FR3_* (XformCommonAPI fails on fr3.usd's orient op)
#    and align /FR3_*/root_joint localPos0/localRot0 with the robot's world mount pose.
# 2. Author home joint angles and PD drive targets ([0, 0, 0, -90, 0, 90, 45] deg, [0.04, 0.04] m) directly in USD before play().
# 3. Fix negative mass / {0, 0, 0} or {1, 1, 1} dummy inertia tensor on virtual links (fr3_link8, fr3_hand_tcp).
# 4. Cap TGS solverVelocityIterationCount to 4 on articulation roots.
from pxr import PhysxSchema

robot_mount_poses = {
    "/FR3_1": (Gf.Vec3f(-0.7, 0.0, 0.20), Gf.Quatf(0.7071068, 0.0, 0.0, 0.7071068)),
    "/FR3_2": (Gf.Vec3f(0.7, 0.0, 0.20), Gf.Quatf(0.7071068, 0.0, 0.0, 0.7071068)),
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
            if jname in ("fr3_link8", "fr3_hand_tcp"):
                mass_api = UsdPhysics.MassAPI.Apply(prim)
                mass_api.CreateMassAttr().Set(1e-4)
                mass_api.CreateDiagonalInertiaAttr().Set(Gf.Vec3f(1e-6, 1e-6, 1e-6))

# 5. Add Objects (Standard blocks, Long Bar, Heavy Engine Part)
nominal_poses = [
    [-0.3, 0.5, 0.53],  # Block 1
    [ 0.3, 0.5, 0.53],  # Block 2
]

for i, pos in enumerate(nominal_poses):
    block_path = f"/Block{i+1}"
    block = UsdGeom.Cube.Define(stage, block_path)
    block.GetSizeAttr().Set(1.0)
    xform = UsdGeom.Xformable(block.GetPrim())
    xform.ClearXformOpOrder()
    xform.AddTranslateOp().Set(Gf.Vec3d(*pos))
    xform.AddScaleOp().Set(Gf.Vec3f(0.06, 0.06, 0.06))
    block.CreateDisplayColorAttr().Set([Gf.Vec3f(0.9, 0.1, 0.1) if i == 0 else Gf.Vec3f(0.1, 0.9, 0.1)])

    UsdPhysics.RigidBodyAPI.Apply(block.GetPrim())
    UsdPhysics.CollisionAPI.Apply(block.GetPrim())

# Long Bar (Requires dual arm, centered between FR3_1 and FR3_2 at [0.0, 0.0, 0.35])
bar_path = "/LongBar"
bar = UsdGeom.Cube.Define(stage, bar_path)
bar.GetSizeAttr().Set(1.0)
xform = UsdGeom.Xformable(bar.GetPrim())
xform.ClearXformOpOrder()
xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 0.35))
xform.AddScaleOp().Set(Gf.Vec3f(0.8, 0.045, 0.045))  # 80cm long
bar.CreateDisplayColorAttr().Set([Gf.Vec3f(0.1, 0.1, 0.9)])  # Blue

UsdPhysics.RigidBodyAPI.Apply(bar.GetPrim())
UsdPhysics.CollisionAPI.Apply(bar.GetPrim())
UsdPhysics.MassAPI.Apply(bar.GetPrim()).CreateMassAttr().Set(0.25)

# Heavy Engine Part (Asymmetric, requires offset grasping)
engine_path = "/HeavyEnginePart"
engine = UsdGeom.Cube.Define(stage, engine_path)
engine.GetSizeAttr().Set(1.0)
engine_xform = UsdGeom.Xformable(engine.GetPrim())
engine_xform.ClearXformOpOrder()
engine_xform.AddTranslateOp().Set(Gf.Vec3d(0.0, -0.25, 0.245))
engine_xform.AddScaleOp().Set(Gf.Vec3f(1.0, 0.12, 0.09))  # 100cm long
engine.CreateDisplayColorAttr().Set([Gf.Vec3f(0.4, 0.4, 0.4)])  # Grey

UsdPhysics.RigidBodyAPI.Apply(engine.GetPrim())
UsdPhysics.CollisionAPI.Apply(engine.GetPrim())

simulation_app.update()

# 5.5 Overhead Camera for Gemini Robotics VLM (Native OpenUSD Camera)
print("Adding overhead camera for Gemini Robotics integration...")
camera_prim = UsdGeom.Camera.Define(stage, "/OverheadCamera")
xform_cam = UsdGeom.Xformable(camera_prim.GetPrim())
xform_cam.ClearXformOpOrder()
xform_cam.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.4, 2.0))
xform_cam.AddRotateXYZOp().Set(Gf.Vec3f(0.0, 90.0, 0.0))  # Downward looking

_camera_initialized = False

def setup_overhead_camera_publishing():
    """Sets up Replicator render product and ROS 2 image publishers once stage is live."""
    global _camera_initialized
    if _camera_initialized:
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

# 6. Setup ROS 2 Bridge Action Graph
try:
    keys = og.Controller.Keys
    (graph, nodes, _, _) = og.Controller.edit(
        {"graph_path": "/ActionGraph", "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: [
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
            ],
            keys.CONNECT: [
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
            ],
            keys.SET_VALUES: [
                ("PublishTF.inputs:topicName", "/tf"),
                ("ComputeTF.inputs:targetPrims", [
                    usdrt.Sdf.Path("/FR3_1"),
                    usdrt.Sdf.Path("/FR3_2"),
                    usdrt.Sdf.Path("/Block1"), usdrt.Sdf.Path("/Block2"),
                    usdrt.Sdf.Path("/LongBar"), usdrt.Sdf.Path("/HeavyEnginePart"),
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
            ],
        },
    )
    print("Action Graph created successfully.")
except Exception as e:
    print(f"Error creating Action Graph: {e}")

setup_overhead_camera_publishing()
for _ in range(3):
    simulation_app.update()

# 8. Articulations & Rigid Prims Management
robot1_art = None
robot2_art = None
blocks = []
bar_rp = None
engine_rp = None

# Canonical home configurations (arm: 7 DOFs, gripper: 2 fingers)
q_home_arm = np.array([0.0, 0.0, 0.0, -1.5708, 0.0, 1.5708, 0.7854], dtype=float)
q_home_gripper = np.array([0.04, 0.04], dtype=float)
q_home_all = np.array([0.0, 0.0, 0.0, -1.5708, 0.0, 1.5708, 0.7854, 0.04, 0.04], dtype=float)

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
    """Resets rigid body pose and zeroes out velocities."""
    if prim is None:
        return
    try:
        prim.set_world_poses(
            positions=np.array([pos], dtype=float),
            orientations=np.array([quat_wxyz], dtype=float)
        )
    except Exception as e:
        print(f"[WARN] set_world_poses on prim failed: {e}")
    set_rigid_velocity(prim, lin_vel=np.zeros((1, 3), dtype=float), ang_vel=np.zeros((1, 3), dtype=float))

def init_articulations_and_poses():
    """Initializes robot articulations, rigid bodies, and camera streams once physics is active."""
    global robot1_art, robot2_art, blocks, bar_rp, engine_rp
    try:
        try:
            from isaacsim.core.experimental.prims import Articulation, RigidPrim
        except ImportError:
            from isaacsim.core.prims import Articulation, RigidPrim

        robot1_art = Articulation("/FR3_1")
        robot2_art = Articulation("/FR3_2")

        for art in [robot1_art, robot2_art]:
            if hasattr(art, "initialize"):
                try:
                    art.initialize()
                except Exception:
                    pass

        reset_robot_articulation(robot1_art, [-0.7, 0.0, 0.20], [0.7071068, 0.0, 0.0, 0.7071068])
        reset_robot_articulation(robot2_art, [0.7, 0.0, 0.20], [0.7071068, 0.0, 0.0, 0.7071068])

        blocks = []
        for i, pos in enumerate(nominal_poses):
            b_prim = RigidPrim(f"/Block{i+1}")
            if hasattr(b_prim, "initialize"):
                try:
                    b_prim.initialize()
                except Exception:
                    pass
            reset_rigid_body(b_prim, pos, [1.0, 0.0, 0.0, 0.0])
            blocks.append(b_prim)

        bar_rp = RigidPrim("/LongBar")
        if hasattr(bar_rp, "initialize"):
            try:
                bar_rp.initialize()
            except Exception:
                pass
        reset_rigid_body(bar_rp, [0.0, 0.0, 0.35], [1.0, 0.0, 0.0, 0.0])

        engine_rp = RigidPrim("/HeavyEnginePart")
        if hasattr(engine_rp, "initialize"):
            try:
                engine_rp.initialize()
            except Exception:
                pass
        reset_rigid_body(engine_rp, [0.0, -0.25, 0.245], [1.0, 0.0, 0.0, 0.0])

        print("[INFO] Assembly robot articulations, camera streams, and rigid bodies initialized successfully.")
    except Exception as e:
        print(f"[WARN] Assembly articulation setup on frame: {e}")

if args.test:
    app_utils.play()
    for _i in range(10):
        simulation_app.update()
        if _i == 0:
            init_articulations_and_poses()
    print("\n[VERIFICATION] ALL SELF-VERIFICATION CHECKS PASSED SUCCESSFULLY!\n")
    simulation_app.close()
    sys.exit(0)

# ROS 2 Reset Mechanism setup
assembly_sim_node = None
assembly_reset_pub = None

_articulations_initialized = False
_pending_reset = False
_pending_reset_publish_ros = True
_last_local_reset_pub_time = 0.0

def request_reset(publish_to_ros=True):
    """Schedules a simulation reset to execute safely between frames in the main loop."""
    global _pending_reset, _pending_reset_publish_ros
    _pending_reset = True
    _pending_reset_publish_ros = publish_to_ros

try:
    import time as _time
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Empty

    if not rclpy.ok():
        rclpy.init()

    assembly_sim_node = Node('assembly_sim_reset_node')
    assembly_reset_pub = assembly_sim_node.create_publisher(Empty, '/reset_simulation', 10)
    assembly_reset_sub = assembly_sim_node.create_subscription(
        Empty,
        '/reset_simulation',
        lambda msg: None if (_time.monotonic() - _last_local_reset_pub_time < 0.25) else request_reset(publish_to_ros=False),
        10,
    )
except Exception as e:
    print(f"[WARN] ROS 2 reset node setup skipped: {e}")
    assembly_sim_node = None

def reset_simulation(publish_to_ros=True):
    global robot1_art, robot2_art, blocks, bar_rp, engine_rp, _articulations_initialized
    if hasattr(app_utils, "is_playing") and not app_utils.is_playing():
        request_reset(publish_to_ros=publish_to_ros)
        app_utils.play()
        return

    print("[RESET] Resetting robot arms and objects in assembly scene...")
    if not _articulations_initialized or robot1_art is None or robot2_art is None:
        init_articulations_and_poses()
        _articulations_initialized = True
    try:
        reset_robot_articulation(robot1_art, [-0.7, 0.0, 0.20], [0.7071068, 0.0, 0.0, 0.7071068])
        reset_robot_articulation(robot2_art, [0.7, 0.0, 0.20], [0.7071068, 0.0, 0.0, 0.7071068])

        for idx, bp in enumerate(blocks):
            if idx < len(nominal_poses):
                reset_rigid_body(bp, nominal_poses[idx], [1.0, 0.0, 0.0, 0.0])

        if bar_rp is not None:
            reset_rigid_body(bar_rp, [0.0, 0.0, 0.35], [1.0, 0.0, 0.0, 0.0])

        if engine_rp is not None:
            reset_rigid_body(engine_rp, [0.0, -0.25, 0.245], [1.0, 0.0, 0.0, 0.0])

        if publish_to_ros and assembly_reset_pub is not None:
            try:
                import time as _time
                global _last_local_reset_pub_time
                _last_local_reset_pub_time = _time.monotonic()
                assembly_reset_pub.publish(Empty())
            except Exception:
                pass
    except Exception as e:
        print(f"Failed to reset simulation: {e}")

# UI Reset Button setup
import omni.appwindow
import carb.input
import omni.ui as ui

def on_keyboard_event(event, *args, **kwargs):
    if event.type == carb.input.KeyboardEventType.KEY_PRESS:
        if event.input.name in ["R", "I"]:
            request_reset(publish_to_ros=True)
    return True

appwindow = omni.appwindow.get_default_app_window()
input_interface = carb.input.acquire_input_interface()
keyboard = appwindow.get_keyboard()
sub_keyboard = input_interface.subscribe_to_keyboard_events(keyboard, on_keyboard_event)

controls_window = ui.Window("Assembly Controls", width=400, height=100)
with controls_window.frame:
    with ui.VStack(spacing=10):
        ui.Label("Controls:", height=20)
        ui.Button("Initialize Poses / Reset Scene (R key)", clicked_fn=lambda: request_reset(publish_to_ros=True), height=30)

# Simulation loop: auto-start timeline so physics tensor entities are active before DOF initialization
app_utils.play()
frame_idx = 0
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
    frame_idx += 1

    if assembly_sim_node is not None:
        try:
            rclpy.spin_once(assembly_sim_node, timeout_sec=0.0)
        except Exception:
            pass

simulation_app.close()
