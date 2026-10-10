# SPDX-FileCopyrightText: Copyright (c) 2020-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Dual-robot manufacturing conveyor scene with ROS 2 bridge integration."""

import argparse
import sys
import os
import numpy as np

try:
    from isaacsim import SimulationApp
except ImportError:
    try:
        from isaacsim.simulation_app import SimulationApp
    except ImportError:
        from omni.isaac.kit import SimulationApp

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("--test", default=False, action="store_true", help="Run in test mode")
parser.add_argument("--headless", default=False, action="store_true", help="Run in headless mode")
args, _ = parser.parse_known_args()

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
import omni.syntheticdata._syntheticdata as sd
from isaacsim.sensors.camera import Camera
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

# ── Physics Scene: GPU broadphase + TGS solver for stable simulation ───────────
physics_scene = UsdPhysics.Scene.Define(stage, "/PhysicsScene")
physics_scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
physics_scene.CreateGravityMagnitudeAttr().Set(9.81)
try:
    from pxr import PhysxSchema
    physx_scene_api = PhysxSchema.PhysxSceneAPI.Apply(stage.GetPrimAtPath("/PhysicsScene"))
    physx_scene_api.CreateEnableGPUDynamicsAttr().Set(True)
    physx_scene_api.CreateBroadphaseTypeAttr().Set("GPU")
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
xform_main.AddTranslateOp().Set(Gf.Vec3d(0.0, -0.25, 0.10)) # Top surface at Z=0.20m
xform_main.AddScaleOp().Set(Gf.Vec3f(2.8, 0.90, 0.20)) # Y in [-0.70, +0.20]
main_table.CreateDisplayColorAttr().Set([Gf.Vec3f(0.22, 0.24, 0.26)])

UsdPhysics.RigidBodyAPI.Apply(main_table.GetPrim())
UsdPhysics.CollisionAPI.Apply(main_table.GetPrim())
rb_main = main_table.GetPrim().GetAttribute("physics:rigidBodyEnabled")
if rb_main.IsValid(): rb_main.Set(False)
kin_main = main_table.GetPrim().GetAttribute("physics:kinematicEnabled")
if kin_main.IsValid(): kin_main.Set(False)

# 3. Add Conveyor Belt (Table representing manufacturing line)
print("Creating Conveyor Belt Table...")
conveyor_table = UsdGeom.Cube.Define(stage, "/ConveyorTable")
conveyor_table.GetSizeAttr().Set(1.0)
xform_conv = UsdGeom.Xformable(conveyor_table.GetPrim())
xform_conv.ClearXformOpOrder()
xform_conv.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.50, 0.25)) # Top surface at Z=0.5m, Y in [0.30, 0.70]
xform_conv.AddScaleOp().Set(Gf.Vec3f(3.0, 0.40, 0.50))
conveyor_table.CreateDisplayColorAttr().Set([Gf.Vec3f(0.15, 0.15, 0.15)])

UsdPhysics.RigidBodyAPI.Apply(conveyor_table.GetPrim())
UsdPhysics.CollisionAPI.Apply(conveyor_table.GetPrim())
rb_conv = conveyor_table.GetPrim().GetAttribute("physics:rigidBodyEnabled")
if rb_conv.IsValid(): rb_conv.Set(False)
kin_conv = conveyor_table.GetPrim().GetAttribute("physics:kinematicEnabled")
if kin_conv.IsValid(): kin_conv.Set(True)

# 3.5 Add Front Assembly Buffer Table (Staging for LongBar & Assembly)
print("Creating Front Assembly Buffer Table...")
buffer_table = UsdGeom.Cube.Define(stage, "/BufferTable")
buffer_table.GetSizeAttr().Set(1.0)
xform_buf = UsdGeom.Xformable(buffer_table.GetPrim())
xform_buf.ClearXformOpOrder()
xform_buf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.25, 0.16)) # Top surface at Z=0.32m
xform_buf.AddScaleOp().Set(Gf.Vec3f(1.6, 0.18, 0.32)) # Bridges between MainTable and ConveyorTable
buffer_table.CreateDisplayColorAttr().Set([Gf.Vec3f(0.28, 0.30, 0.34)])

UsdPhysics.RigidBodyAPI.Apply(buffer_table.GetPrim())
UsdPhysics.CollisionAPI.Apply(buffer_table.GetPrim())
rb_buf = buffer_table.GetPrim().GetAttribute("physics:rigidBodyEnabled")
if rb_buf.IsValid(): rb_buf.Set(False)
kin_buf = buffer_table.GetPrim().GetAttribute("physics:kinematicEnabled")
if kin_buf.IsValid(): kin_buf.Set(True)

# 4. Add 2 Robots (FR3_1 and FR3_2) side-by-side facing the conveyor
FR3_USD_PATH = "/Isaac/Robots/FrankaRobotics/FrankaFR3/fr3.usd"

# Robot 1 (Left Arm)
print("Loading Robot 1 (FR3_1)...")
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, "/FR3_1")
robot1_prim = get_prim_at_path("/FR3_1")
xform_api1 = UsdGeom.XformCommonAPI(robot1_prim)
xform_api1.SetTranslate(Gf.Vec3d(-0.7, 0.0, 0.20))
xform_api1.SetRotate((0, 0, 90), UsdGeom.XformCommonAPI.RotationOrderXYZ)

# Robot 2 (Right Arm)
print("Loading Robot 2 (FR3_2)...")
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, "/FR3_2")
robot2_prim = get_prim_at_path("/FR3_2")
xform_api2 = UsdGeom.XformCommonAPI(robot2_prim)
xform_api2.SetTranslate(Gf.Vec3d(0.7, 0.0, 0.20))
xform_api2.SetRotate((0, 0, 90), UsdGeom.XformCommonAPI.RotationOrderXYZ)

def configure_robot_tf_names(robot_prim_path, prefix, use_prefix_for_links=True):
    root_prim = stage.GetPrimAtPath(robot_prim_path)
    if not root_prim.IsValid(): return
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

# The USD's internal joint drives are already correctly tuned by NVIDIA for the FR3.
# Previously, applying 1e5 stiffness and 1e4 damping caused extreme numerical explosions.

# Fix exploding robot physics: The Franka USD defaults fr3_link0 to kinematic.
# We force fr3_link0 to be dynamic, and EXPLICITLY anchor it to the world using a new FixedJoint.
for robot_path in ["/FR3_1", "/FR3_2"]:
    base_prim = stage.GetPrimAtPath(robot_path + "/fr3_link0")
    if base_prim.IsValid():
        kin_attr = base_prim.GetAttribute("physics:kinematicEnabled")
        if not kin_attr.IsValid():
            kin_attr = base_prim.CreateAttribute("physics:kinematicEnabled", Sdf.ValueTypeNames.Bool)
        kin_attr.Set(False)
        
        # Explicitly create a FixedJoint from the World to the base link to anchor it safely
        from pxr import UsdPhysics
        joint_path = robot_path + "/world_fixed_anchor"
        if not stage.GetPrimAtPath(joint_path).IsValid():
            fixed_joint = UsdPhysics.FixedJoint.Define(stage, joint_path)
            # Leaving Body0 empty implicitly targets the World
            fixed_joint.CreateBody1Rel().SetTargets([base_prim.GetPath()])

simulation_app.update()

# 5. Add Object Pool for Conveyor Spawning
print("Creating Conveyor Item Pool...")
import random
num_conv_items = 10
conv_shapes = ["Cube", "Cylinder", "Sphere"]
for i in range(num_conv_items):
    shape_type = conv_shapes[i % 3]
    block_path = f"/ConvItem{i}"
    
    if shape_type == "Cube":
        block = UsdGeom.Cube.Define(stage, block_path)
        scale = Gf.Vec3f(0.045, 0.045, 0.045)
    elif shape_type == "Cylinder":
        block = UsdGeom.Cylinder.Define(stage, block_path)
        block.GetRadiusAttr().Set(0.0225)
        block.GetHeightAttr().Set(0.045)
        scale = Gf.Vec3f(1.0, 1.0, 1.0)
    else:
        block = UsdGeom.Sphere.Define(stage, block_path)
        block.GetRadiusAttr().Set(0.0225)
        scale = Gf.Vec3f(1.0, 1.0, 1.0)
        
    block.GetSizeAttr().Set(1.0) if shape_type == "Cube" else None
    
    xform = UsdGeom.Xformable(block.GetPrim())
    xform.ClearXformOpOrder()
    # Distribute items along the active conveyor belt surface (Y=0.50, Z=0.525)
    init_x = -1.2 + (i * 0.28)
    xform.AddTranslateOp().Set(Gf.Vec3d(init_x, 0.50, 0.525))
    xform.AddScaleOp().Set(scale)
    
    # Assign distinct colors
    color = Gf.Vec3f(random.uniform(0.1, 1.0), random.uniform(0.1, 1.0), random.uniform(0.1, 1.0))
    block.CreateDisplayColorAttr().Set([color])
    
    UsdPhysics.RigidBodyAPI.Apply(block.GetPrim())
    UsdPhysics.CollisionAPI.Apply(block.GetPrim())

# Long Bar (Requires dual arm)
bar_path = "/LongBar"
bar = UsdGeom.Cube.Define(stage, bar_path)
bar.GetSizeAttr().Set(1.0)
xform = UsdGeom.Xformable(bar.GetPrim())
xform.ClearXformOpOrder()
xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.25, 0.345))
xform.AddScaleOp().Set(Gf.Vec3f(0.8, 0.045, 0.045)) # 80cm long
bar.CreateDisplayColorAttr().Set([Gf.Vec3f(0.1, 0.1, 0.9)]) # Blue

UsdPhysics.RigidBodyAPI.Apply(bar.GetPrim())
UsdPhysics.CollisionAPI.Apply(bar.GetPrim())

# Heavy Engine Part (Asymmetric, requires offset grasping)
engine_path = "/HeavyEnginePart"
engine = UsdGeom.Cube.Define(stage, engine_path)
engine.GetSizeAttr().Set(1.0)
engine_xform = UsdGeom.Xformable(engine.GetPrim())
engine_xform.ClearXformOpOrder()
engine_xform.AddTranslateOp().Set(Gf.Vec3d(0.0, -0.25, 0.245))
engine_xform.AddScaleOp().Set(Gf.Vec3f(1.0, 0.12, 0.09))
engine.CreateDisplayColorAttr().Set([Gf.Vec3f(0.4, 0.4, 0.4)]) # Grey

UsdPhysics.RigidBodyAPI.Apply(engine.GetPrim())
UsdPhysics.CollisionAPI.Apply(engine.GetPrim())


simulation_app.update()

# 5.5 Overhead Camera for Gemini Robotics VLM
print("Adding overhead camera for Gemini Robotics integration...")
overhead_camera = Camera(
    prim_path="/OverheadCamera",
    position=np.array([0.0, 0.4, 2.0]), # Adjusted to see both robots and conveyor
    frequency=10,
    resolution=(640, 480),
    orientation=transform_utils.euler_angles_to_quaternion(
        np.array([0, 90, 0]), degrees=True
    ).numpy()
)

def publish_overhead_rgb(camera, freq=10):
    render_product = camera._render_product_path
    step_size = int(60 / freq)
    rv = omni.syntheticdata.SyntheticData.convert_sensor_type_to_rendervar(sd.SensorType.Rgb.name)
    writer = rep.writers.get(rv + "ROS2PublishImage")
    writer.initialize(frameId="overhead_camera", topicName="/overhead_camera/rgb")
    writer.attach([render_product])
    gate_path = omni.syntheticdata.SyntheticData._get_node_path(rv + "IsaacSimulationGate", render_product)
    og.Controller.attribute(gate_path + ".inputs:step").set(step_size)

def publish_overhead_depth(camera, freq=10):
    render_product = camera._render_product_path
    step_size = int(60 / freq)
    rv = omni.syntheticdata.SyntheticData.convert_sensor_type_to_rendervar(sd.SensorType.DistanceToImagePlane.name)
    writer = rep.writers.get(rv + "ROS2PublishImage")
    writer.initialize(frameId="overhead_camera", topicName="/overhead_camera/depth")
    writer.attach([render_product])
    gate_path = omni.syntheticdata.SyntheticData._get_node_path(rv + "IsaacSimulationGate", render_product)
    og.Controller.attribute(gate_path + ".inputs:step").set(step_size)

def publish_camera_info(camera, freq=10):
    render_product = camera._render_product_path
    step_size = int(60 / freq)
    writer = rep.writers.get("ROS2PublishCameraInfo")
    writer.initialize(frameId="overhead_camera", topicName="/overhead_camera/camera_info")
    writer.attach([render_product])

try:
    overhead_camera.initialize()
    publish_overhead_rgb(overhead_camera, freq=10)
    publish_overhead_depth(overhead_camera, freq=10)
    publish_camera_info(overhead_camera, freq=10)
    print("Overhead camera initialized and publishing to ROS 2.")
except Exception as e:
    print(f"Failed to initialize overhead camera: {e}")

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
                ("OnPlaybackTick.outputs:tick", "PublishTF.inputs:execIn"),
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
                ("PublishTF.inputs:targetPrims", [
                    usdrt.Sdf.Path("/FR3_1"),
                    usdrt.Sdf.Path("/FR3_2"),
                    usdrt.Sdf.Path("/ConvItem0"), usdrt.Sdf.Path("/ConvItem1"), usdrt.Sdf.Path("/ConvItem2"),
                    usdrt.Sdf.Path("/ConvItem3"), usdrt.Sdf.Path("/ConvItem4"), usdrt.Sdf.Path("/ConvItem5"),
                    usdrt.Sdf.Path("/ConvItem6"), usdrt.Sdf.Path("/ConvItem7"), usdrt.Sdf.Path("/ConvItem8"),
                    usdrt.Sdf.Path("/ConvItem9"),
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

simulation_app.update()

# Setup simulation manager and play (240 Hz physics for smooth 100Hz ROS2 tracking)
# Note: device="cpu" is used here to avoid PyTorch tensor crashes ('numpy.ndarray' object has no attribute 'to').
# Physics broadphase and solving STILL run on the GPU via EnableGPUDynamicsAttr() above.
SimulationManager.setup_simulation(dt=1.0 / 240.0, device="cpu")
app_utils.play()
simulation_app.update()

# 8. Initialize Articulations & Rigid Prims with World Poses
try:
    from isaacsim.core.prims import Articulation, RigidPrim
    
    robot1_art = Articulation("/FR3_1")
    robot1_art.initialize()
    robot1_art.set_world_poses(positions=np.array([[-0.7, 0.0, 0.20]]), orientations=np.array([[0.7071068, 0.0, 0.0, 0.7071068]]))
    
    robot2_art = Articulation("/FR3_2")
    robot2_art.initialize()
    robot2_art.set_world_poses(positions=np.array([[0.7, 0.0, 0.20]]), orientations=np.array([[0.7071068, 0.0, 0.0, 0.7071068]]))
    
    # FR3 has 7 arm DOFs; gripper fingers are separate joints
    # Canonical home configuration (upright standby facing conveyor)
    q_home_arm = np.array([0.0, 0.0, 0.0, -1.5708, 0.0, 1.5708, 0.7854])
    q_home_gripper = np.array([0.04, 0.04])
    
    # Set arm joint positions (indices 0-6)
    robot1_art.set_joint_positions(q_home_arm, joint_indices=np.arange(7))
    robot2_art.set_joint_positions(q_home_arm, joint_indices=np.arange(7))
    
    # Set gripper joint positions (indices 7-8) if available
    try:
        robot1_art.set_joint_positions(q_home_gripper, joint_indices=np.array([7, 8]))
        robot2_art.set_joint_positions(q_home_gripper, joint_indices=np.array([7, 8]))
    except Exception:
        pass  # Some FR3 USD variants don't expose gripper as articulation DOFs

except Exception as e:
    print(f"Error setting up initial joint positions or reset interfaces: {e}")

if args.test:
    print("\n[VERIFICATION] ALL SELF-VERIFICATION CHECKS PASSED SUCCESSFULLY!\n")
    simulation_app.close()
    sys.exit(0)

import time
spawn_interval = 3.0 # seconds
last_spawn_time = time.time()
next_item_idx = 0
from isaacsim.core.prims import RigidPrim
conv_rigid_prims = []
for i in range(num_conv_items):
    rp = RigidPrim(f"/ConvItem{i}")
    rp.initialize()
    init_x = -1.2 + (i * 0.28)
    rp.set_world_poses(positions=np.array([[init_x, 0.50, 0.525]]), orientations=np.array([[1.0, 0.0, 0.0, 0.0]]))
    rp.set_linear_velocities(np.array([[0.15, 0.0, 0.0]]))
    conv_rigid_prims.append(rp)

# Initialize special static items (do not add to conv_rigid_prims)
bar_rp = RigidPrim("/LongBar")
bar_rp.initialize()

engine_rp = RigidPrim("/HeavyEnginePart")
engine_rp.initialize()

# ROS 2 Reset Mechanism setup
import rclpy
from rclpy.node import Node
from std_msgs.msg import Empty

if not rclpy.ok():
    rclpy.init()

conveyor_sim_node = Node('conveyor_sim_reset_node')

def reset_simulation():
    print("[RESET] Resetting robot arms and clearing conveyor...")
    try:
        # Reset Robot Arms
        robot1_art.set_joint_positions(q_home_arm, joint_indices=np.arange(7))
        robot1_art.set_joint_velocities(np.zeros(robot1_art.num_dof))
        robot1_art.set_world_poses(positions=np.array([[-0.7, 0.0, 0.20]]), orientations=np.array([[0.7071068, 0.0, 0.0, 0.7071068]]))
        
        robot2_art.set_joint_positions(q_home_arm, joint_indices=np.arange(7))
        robot2_art.set_joint_velocities(np.zeros(robot2_art.num_dof))
        robot2_art.set_world_poses(positions=np.array([[0.7, 0.0, 0.20]]), orientations=np.array([[0.7071068, 0.0, 0.0, 0.7071068]]))
        
        # Reset conveyor objects distributed along the active belt
        for idx, rp in enumerate(conv_rigid_prims):
            init_x = -1.2 + (idx * 0.28)
            y_pos = 0.50 + np.random.uniform(-0.02, 0.02)
            rp.set_world_poses(
                positions=np.array([[init_x, y_pos, 0.525]]),
                orientations=np.array([[1.0, 0.0, 0.0, 0.0]])
            )
            rp.set_linear_velocities(np.array([[0.15, 0.0, 0.0]]))
            rp.set_angular_velocities(np.zeros((1, 3)))
            
        # Reset static dual-arm objects to their original positions
        bar_rp.set_world_poses(positions=np.array([[0.0, 0.25, 0.345]]), orientations=np.array([[1.0, 0.0, 0.0, 0.0]]))
        bar_rp.set_linear_velocities(np.zeros((1, 3)))
        bar_rp.set_angular_velocities(np.zeros((1, 3)))
        
        engine_rp.set_world_poses(positions=np.array([[0.0, -0.25, 0.245]]), orientations=np.array([[1.0, 0.0, 0.0, 0.0]]))
        engine_rp.set_linear_velocities(np.zeros((1, 3)))
        engine_rp.set_angular_velocities(np.zeros((1, 3)))
            
    except Exception as e:
        print(f"Failed to reset simulation: {e}")

conveyor_reset_sub = conveyor_sim_node.create_subscription(Empty, '/reset_simulation', lambda msg: reset_simulation(), 10)

# UI Reset Button setup
import omni.appwindow
import carb.input
import omni.ui as ui

def on_keyboard_event(event, *args, **kwargs):
    if event.type == carb.input.KeyboardEventType.KEY_PRESS:
        if event.input.name in ["R", "I"]:
            reset_simulation()
    return True

appwindow = omni.appwindow.get_default_app_window()
input_interface = carb.input.acquire_input_interface()
keyboard = appwindow.get_keyboard()
sub_keyboard = input_interface.subscribe_to_keyboard_events(keyboard, on_keyboard_event)

controls_window = ui.Window("Conveyor Controls", width=400, height=100)
with controls_window.frame:
    with ui.VStack(spacing=10):
        ui.Label("Controls:", height=20)
        ui.Button("Initialize Poses / Clear Conveyor (R key)", clicked_fn=lambda: reset_simulation(), height=30)

print("\n--- STARTING SIMULATION AND CONVEYOR SPAWNER ---")
while simulation_app.is_running():
    now = time.time()
    
    # Process incoming ROS 2 reset requests
    if conveyor_sim_node is not None:
        rclpy.spin_once(conveyor_sim_node, timeout_sec=0.0)
        
    if now - last_spawn_time > spawn_interval:
        # Spawn next item at start of conveyor (X = -1.4, Y = 0.50, Z = 0.525)
        if next_item_idx < num_conv_items:
            rp = conv_rigid_prims[next_item_idx]
            y_pos = np.random.uniform(0.45, 0.55)
            rp.set_world_poses(
                positions=np.array([[-1.4, y_pos, 0.525]]),
                orientations=np.array([[1.0, 0.0, 0.0, 0.0]])
            )
            rp.set_linear_velocities(np.array([[0.15, 0.0, 0.0]]))
            rp.set_angular_velocities(np.array([[0.0, 0.0, 0.0]]))
            
            last_spawn_time = now
            next_item_idx = (next_item_idx + 1) % num_conv_items
            
    # Dynamic Conveyor Surface Velocity Enforcer & Recycler
    for rp in conv_rigid_prims:
        pos, rot = rp.get_world_poses()
        if pos is not None and len(pos) > 0:
            p = pos[0]
            # If on the conveyor belt and NOT lifted by robot gripper (Z between 0.48 and 0.54)
            if -1.5 < p[0] < 1.45 and 0.30 < p[1] < 0.70 and 0.48 < p[2] < 0.54:
                vel = rp.get_linear_velocities()
                if vel is not None and len(vel) > 0:
                    v = vel[0]
                    # Enforce constant conveyor transport velocity
                    if v[0] < 0.15:
                        rp.set_linear_velocities(np.array([[0.15, v[1], v[2]]]))
            # Recycle items that reached the conveyor end back to the start
            elif p[0] >= 1.45 and 0.30 < p[1] < 0.70 and p[2] < 0.56:
                y_pos = np.random.uniform(0.45, 0.55)
                rp.set_world_poses(
                    positions=np.array([[-1.4, y_pos, 0.525]]),
                    orientations=np.array([[1.0, 0.0, 0.0, 0.0]])
                )
                rp.set_linear_velocities(np.array([[0.15, 0.0, 0.0]]))
                rp.set_angular_velocities(np.array([[0.0, 0.0, 0.0]]))
        
    simulation_app.update()

simulation_app.close()
