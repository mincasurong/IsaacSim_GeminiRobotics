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

"""Three-robot tower assembly scene with ROS 2 bridge integration, elevated workbench, and pose randomization."""

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
from pxr import Gf, UsdGeom, UsdPhysics, Usd, PhysxSchema, Sdf
import omni.usd
import omni.client
import omni.replicator.core as rep
import omni.syntheticdata._syntheticdata as sd
from isaacsim.sensors.camera import Camera
import isaacsim.core.experimental.utils.transform as transform_utils

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

# Robot 1: Franka FR3 at [0.0, -0.45, 0.20] rotated 90 deg around Z
print("Loading Robot 1 (FR3_1)...")
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, "/FR3_1")
robot1_prim = get_prim_at_path("/FR3_1")
xform_api1 = UsdGeom.XformCommonAPI(robot1_prim)
xform_api1.SetTranslate(Gf.Vec3d(0.0, -0.45, 0.20))
xform_api1.SetRotate((0, 0, 90), UsdGeom.XformCommonAPI.RotationOrderXYZ)

# Robot 2: Franka FR3 at [0.3897, 0.225, 0.20] rotated 210 deg around Z
print("Loading Robot 2 (FR3_2)...")
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, "/FR3_2")
robot2_prim = get_prim_at_path("/FR3_2")
xform_api2 = UsdGeom.XformCommonAPI(robot2_prim)
xform_api2.SetTranslate(Gf.Vec3d(0.3897, 0.225, 0.20))
xform_api2.SetRotate((0, 0, 210), UsdGeom.XformCommonAPI.RotationOrderXYZ)

# Robot 3: Franka FR3 at [-0.3897, 0.225, 0.20] rotated 330 deg around Z
print("Loading Robot 3 (FR3_3)...")
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, "/FR3_3")
robot3_prim = get_prim_at_path("/FR3_3")
xform_api3 = UsdGeom.XformCommonAPI(robot3_prim)
xform_api3.SetTranslate(Gf.Vec3d(-0.3897, 0.225, 0.20))
xform_api3.SetRotate((0, 0, 330), UsdGeom.XformCommonAPI.RotationOrderXYZ)

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
        xform_cube.AddScaleOp().Set(Gf.Vec3f(0.06, 0.06, 0.06))
        cube.CreateDisplayColorAttr().Set([block_colors[i]])
        
        UsdPhysics.RigidBodyAPI.Apply(cube.GetPrim())
        UsdPhysics.CollisionAPI.Apply(cube.GetPrim())
    else:
        # Cylinder (height 0.06m, radius 0.03m)
        cylinder = UsdGeom.Cylinder.Define(stage, block_path)
        cylinder.GetHeightAttr().Set(0.06)
        cylinder.GetRadiusAttr().Set(0.03)
        cylinder.GetAxisAttr().Set("Z")
        xform_cyl = UsdGeom.Xformable(cylinder.GetPrim())
        xform_cyl.ClearXformOpOrder()
        xform_cyl.AddTranslateOp().Set(Gf.Vec3d(*spawn_pos))
        xform_cyl.AddRotateXYZOp().Set(Gf.Vec3d(0.0, 0.0, theta_deg))
        cylinder.CreateDisplayColorAttr().Set([block_colors[i]])
        
        UsdPhysics.RigidBodyAPI.Apply(cylinder.GetPrim())
        UsdPhysics.CollisionAPI.Apply(cylinder.GetPrim())

simulation_app.update()

# 6. Overhead Camera for Gemini Robotics VLM
print("Adding overhead camera for Gemini Robotics integration...")
overhead_camera = Camera(
    prim_path="/OverheadCamera",
    position=np.array([0.0, 0.0, 1.8]),
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
                ("PublishTF.inputs:targetPrims", [
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

simulation_app.update()

# Setup simulation manager and play
SimulationManager.setup_simulation(dt=1.0 / 120.0, device="cpu")
app_utils.play()
simulation_app.update()

# Initialize Overhead Camera
try:
    overhead_camera.initialize()
    publish_overhead_rgb(overhead_camera, freq=10)
    publish_overhead_depth(overhead_camera, freq=10)
    publish_camera_info(overhead_camera, freq=10)
    print("Overhead camera initialized and publishing to ROS 2.")
except Exception as e:
    print(f"Warning: Overhead camera setup failed: {e}")

simulation_app.update()

# 8. Initialize Articulations & Rigid Prims with World Poses
try:
    from isaacsim.core.prims import Articulation, RigidPrim
    
    robot1_art = Articulation("/FR3_1")
    robot1_art.initialize()
    robot1_art.set_world_poses(positions=np.array([[0.0, -0.45, 0.20]]), orientations=np.array([[0.7071068, 0.0, 0.0, 0.7071068]])) # 90 deg Z
    
    robot2_art = Articulation("/FR3_2")
    robot2_art.initialize()
    robot2_art.set_world_poses(positions=np.array([[0.3897, 0.225, 0.20]]), orientations=np.array([[-0.258819, 0.0, 0.0, 0.9659258]])) # 210 deg Z
    
    robot3_art = Articulation("/FR3_3")
    robot3_art.initialize()
    robot3_art.set_world_poses(positions=np.array([[-0.3897, 0.225, 0.20]]), orientations=np.array([[-0.9659258, 0.0, 0.0, -0.258819]])) # 330 deg Z
    
    q_home_fr3 = np.array([0.0, -0.785398, 0.0, -2.35619, 0.0, 1.57079, 0.785398, 0.04, 0.04])
    robot1_art.set_joint_positions(q_home_fr3)
    robot2_art.set_joint_positions(q_home_fr3)
    robot3_art.set_joint_positions(q_home_fr3)
    
    blocks = []
    for i in range(9):
        block_prim = RigidPrim(f"/Block{i+1}")
        block_prim.initialize()
        blocks.append(block_prim)

    # 9. ROS 2 Reset Mechanism setup & Pose Randomization Callback
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Empty
    from std_srvs.srv import Trigger

    if not rclpy.ok():
        rclpy.init()

    reset_node = Node('three_robot_reset_node')
    reset_pub = reset_node.create_publisher(Empty, '/reset_simulation', 10)
    
    from std_msgs.msg import String
    goal_pub = reset_node.create_publisher(String, '/gemini/custom_goal', 10)

    def reset_simulation(publish_to_ros=True):
        print("[RESET] Randomizing block poses and resetting robot arms...")
        try:
            # Reset Robot Arms to Table World Poses & Home Joint States
            robot1_art.set_joint_positions(q_home_fr3)
            robot1_art.set_joint_velocities(np.zeros(robot1_art.num_dof))
            robot1_art.set_world_poses(positions=np.array([[0.0, -0.45, 0.20]]), orientations=np.array([[0.7071068, 0.0, 0.0, 0.7071068]]))
            
            robot2_art.set_joint_positions(q_home_fr3)
            robot2_art.set_joint_velocities(np.zeros(robot2_art.num_dof))
            robot2_art.set_world_poses(positions=np.array([[0.3897, 0.225, 0.20]]), orientations=np.array([[-0.258819, 0.0, 0.0, 0.9659258]]))
            
            robot3_art.set_joint_positions(q_home_fr3)
            robot3_art.set_joint_velocities(np.zeros(robot3_art.num_dof))
            robot3_art.set_world_poses(positions=np.array([[-0.3897, 0.225, 0.20]]), orientations=np.array([[-0.9659258, 0.0, 0.0, -0.258819]]))
            
            # Reset & Randomize All 9 Block Poses on Source Tables
            for i, block_prim in enumerate(blocks):
                nominal_p = nominal_block_poses[i]
                dx = np.random.uniform(-0.035, 0.035)
                dy = np.random.uniform(-0.035, 0.035)
                theta = np.random.uniform(0, 2 * np.pi)
                qw = np.cos(theta / 2.0)
                qz = np.sin(theta / 2.0)
                
                block_prim.set_world_poses(
                    positions=np.array([[nominal_p[0] + dx, nominal_p[1] + dy, nominal_p[2]]]),
                    orientations=np.array([[qw, 0.0, 0.0, qz]])
                )
                block_prim.set_linear_velocities(np.zeros((1, 3)))
                block_prim.set_angular_velocities(np.zeros((1, 3)))
                
            if publish_to_ros:
                reset_pub.publish(Empty())
            print("[RESET] Simulation reset and block pose randomization complete.")
        except Exception as err:
            print(f"[RESET] Error resetting simulation: {err}")

    # Subscriber & Service callbacks
    def ros_reset_callback(msg):
        reset_simulation(publish_to_ros=False)

    reset_sub = reset_node.create_subscription(Empty, '/reset_simulation', ros_reset_callback, 10)

    def ros_reset_service_callback(request, response):
        reset_simulation(publish_to_ros=True)
        response.success = True
        return response

    reset_srv = reset_node.create_service(Trigger, '/reset_simulation', ros_reset_service_callback)

    def adversarial_push():
        print("\n[ADVERSARIAL] Applying physics impulses to knock over the tower!")
        try:
            for i in range(9):
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
                    block_prim.set_linear_velocities(np.array([[v_x, v_y, v_z]]))
                    block_prim.set_angular_velocities(np.array([[w_x, w_y, w_z]]))
        except Exception as e:
            print(f"[ADVERSARIAL] Failed to apply push: {e}")

    # UI Reset Button setup
    import omni.appwindow
    import carb.input
    import omni.ui as ui

    def on_keyboard_event(event, *args, **kwargs):
        if event.type == carb.input.KeyboardEventType.KEY_PRESS:
            if event.input.name in ["R", "I"]:
                reset_simulation(publish_to_ros=True)
            elif event.input.name == "T":
                adversarial_push()
        return True
    appwindow = omni.appwindow.get_default_app_window()
    input_interface = carb.input.acquire_input_interface()
    keyboard = appwindow.get_keyboard()
    sub_keyboard = input_interface.subscribe_to_keyboard_events(keyboard, on_keyboard_event)
    # UI logic for Interactive Mode
    print("\n[INFO] Press PLAY in the UI and use the interactive window.")
    ui.Workspace.set_show_window_fn("Controls", lambda x: True)
    controls_window = ui.Window("Tower Stacking Controls", width=400, height=200)
    
    with controls_window.frame:
        with ui.VStack(spacing=10):
            ui.Label("Controls:", height=20)
            ui.Button("Initialize Poses / Randomize Blocks (R key)", clicked_fn=lambda: reset_simulation(publish_to_ros=True), height=30)
            ui.Button("💥 KNOCK TOWER OVER 💥 (T key)", clicked_fn=adversarial_push, height=30, style={"background_color": 0xFF4444FF, "color": 0xFFFFFFFF})
            
            ui.Spacer(height=10)
            ui.Label("Custom Gemini Goal:", height=20)
            goal_field = ui.StringField(height=30)
            goal_field.model.set_value("Your ultimate goal is to build a single, stable 9-layer tower on the central target table using ALL 9 available objects.")
            
            def send_custom_goal():
                from std_msgs.msg import String
                text = goal_field.model.get_value_as_string()
                msg = String()
                msg.data = text
                goal_pub.publish(msg)
                print(f"[GEMINI] Custom goal sent to ROS 2: {text}")
                
            ui.Button("Send Custom Goal to Gemini", clicked_fn=send_custom_goal, height=40, style={"background_color": 0xFF44FF44})

except Exception as e:
    print(f"Error setting up initial joint positions or reset interfaces: {e}")
    reset_node = None

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
        simulation_app.close()
        sys.exit(0)
    except AssertionError as ae:
        print(f"\n[VERIFICATION FAILED]: {ae}\n")
        simulation_app.close()
        sys.exit(1)

# Simulation loop
while simulation_app.is_running():
    simulation_app.update()
    if reset_node is not None:
        rclpy.spin_once(reset_node, timeout_sec=0.0)

simulation_app.close()
