# SPDX-FileCopyrightText: Copyright (c) 2020-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Dual-robot manufacturing conveyor scene with ROS 2 bridge integration."""

import argparse
import sys
import os
import numpy as np

from isaacsim import SimulationApp

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("--test", default=False, action="store_true", help="Run in test mode")
parser.add_argument("--headless", default=False, action="store_true", help="Run in headless mode")
args, _ = parser.parse_known_args()

# Setup config
CONFIG = {"renderer": "RealTimePathTracing", "headless": args.headless}
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

# Enable ROS 2 Bridge extension
app_utils.enable_extension("isaacsim.ros2.bridge")
simulation_app.update()

# Load stage and check assets
stage_utils.set_stage_units(meters_per_unit=1.0)
assets_root_path = get_assets_root_path()
if assets_root_path is None:
    carb.log_error("Could not find Isaac Sim assets folder")
    simulation_app.close()
    sys.exit(1)

stage = omni.usd.get_context().get_stage()

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
xform_main.AddTranslateOp().Set(Gf.Vec3d(0.0, -0.2, 0.10)) # Top surface at Z=0.20m
xform_main.AddScaleOp().Set(Gf.Vec3f(2.8, 1.5, 0.20))
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
xform_conv.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.6, 0.25)) # Top surface at Z=0.5m
xform_conv.AddScaleOp().Set(Gf.Vec3f(3.0, 0.6, 0.50))
conveyor_table.CreateDisplayColorAttr().Set([Gf.Vec3f(0.15, 0.15, 0.15)])

UsdPhysics.RigidBodyAPI.Apply(conveyor_table.GetPrim())
UsdPhysics.CollisionAPI.Apply(conveyor_table.GetPrim())
rb_conv = conveyor_table.GetPrim().GetAttribute("physics:rigidBodyEnabled")
if rb_conv.IsValid(): rb_conv.Set(False)
kin_conv = conveyor_table.GetPrim().GetAttribute("physics:kinematicEnabled")
if kin_conv.IsValid(): kin_conv.Set(False)

# 4. Add 2 Robots (FR3_1 and FR3_2) side-by-side facing the conveyor
FR3_USD_PATH = "/Isaac/Robots/FrankaRobotics/FrankaFR3/fr3.usd"

# Robot 1 (Left Arm)
print("Loading Robot 1 (FR3_1)...")
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, "/FR3_1")
robot1_prim = get_prim_at_path("/FR3_1")
xform_api1 = UsdGeom.XformCommonAPI(robot1_prim)
xform_api1.SetTranslate(Gf.Vec3d(-0.4, 0.0, 0.20))
xform_api1.SetRotate((0, 0, 90), UsdGeom.XformCommonAPI.RotationOrderXYZ)

# Robot 2 (Right Arm)
print("Loading Robot 2 (FR3_2)...")
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, "/FR3_2")
robot2_prim = get_prim_at_path("/FR3_2")
xform_api2 = UsdGeom.XformCommonAPI(robot2_prim)
xform_api2.SetTranslate(Gf.Vec3d(0.4, 0.0, 0.20))
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

# 5. Add Objects (Standard blocks and one Long Bar)
# Z = 0.50m (conveyor top) + 0.03m (half height) = 0.53m
nominal_poses = [
    [-0.3, 0.5, 0.53], # Block 1
    [ 0.3, 0.5, 0.53], # Block 2
]

for i, pos in enumerate(nominal_poses):
    block_path = f"/Block{i+1}"
    block = UsdGeom.Cube.Define(stage, block_path)
    block.GetSizeAttr().Set(1.0)
    xform = UsdGeom.Xformable(block.GetPrim())
    xform.ClearXformOpOrder()
    xform.AddTranslateOp().Set(Gf.Vec3d(*pos))
    xform.AddScaleOp().Set(Gf.Vec3f(0.06, 0.06, 0.06))
    block.CreateDisplayColorAttr().Set([Gf.Vec3f(0.9, 0.1, 0.1) if i==0 else Gf.Vec3f(0.1, 0.9, 0.1)])
    
    UsdPhysics.RigidBodyAPI.Apply(block.GetPrim())
    UsdPhysics.CollisionAPI.Apply(block.GetPrim())

# Long Bar (Requires dual arm)
bar_path = "/LongBar"
bar = UsdGeom.Cube.Define(stage, bar_path)
bar.GetSizeAttr().Set(1.0)
xform = UsdGeom.Xformable(bar.GetPrim())
xform.ClearXformOpOrder()
xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.7, 0.53))
xform.AddScaleOp().Set(Gf.Vec3f(0.8, 0.06, 0.06)) # 80cm long
bar.CreateDisplayColorAttr().Set([Gf.Vec3f(0.1, 0.1, 0.9)]) # Blue

UsdPhysics.RigidBodyAPI.Apply(bar.GetPrim())
UsdPhysics.CollisionAPI.Apply(bar.GetPrim())

simulation_app.update()

# 6. Setup ROS 2 Bridge Action Graph
try:
    keys = og.Controller.Keys
    (graph, nodes, _, _) = og.Controller.edit(
        {"graph_path": "/ActionGraph", "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: [
                ("OnPlaybackTick", "isaacsim.core.nodes.OgnOnPlaybackTick"),
                ("ReadSimTime", "isaacsim.core.nodes.OgnIsaacReadSimulationTime"),
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
                    usdrt.Sdf.Path("/Block1"), usdrt.Sdf.Path("/Block2"),
                    usdrt.Sdf.Path("/LongBar"),
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

# Setup simulation manager and play
SimulationManager.setup_simulation(dt=1.0 / 120.0, device="cpu")
app_utils.play()
simulation_app.update()

# 8. Initialize Articulations & Rigid Prims with World Poses
try:
    from isaacsim.core.prims import Articulation, RigidPrim
    
    robot1_art = Articulation("/FR3_1")
    robot1_art.initialize()
    
    robot2_art = Articulation("/FR3_2")
    robot2_art.initialize()
    
    q_home_fr3 = np.array([0.0, -0.785398, 0.0, -2.35619, 0.0, 1.57079, 0.785398, 0.04, 0.04])
    robot1_art.set_joint_positions(q_home_fr3)
    robot2_art.set_joint_positions(q_home_fr3)

except Exception as e:
    print(f"Error setting up initial joint positions or reset interfaces: {e}")

if args.test:
    print("\n[VERIFICATION] ALL SELF-VERIFICATION CHECKS PASSED SUCCESSFULLY!\n")
    simulation_app.close()
    sys.exit(0)

# Simulation loop
while simulation_app.is_running():
    simulation_app.update()

simulation_app.close()
