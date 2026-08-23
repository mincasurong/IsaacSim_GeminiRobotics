# SPDX-FileCopyrightText: Copyright (c) 2020-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import argparse
import sys
import numpy as np
from isaacsim import SimulationApp

parser = argparse.ArgumentParser()
parser.add_argument("--test", default=False, action="store_true", help="Run in test mode")
args, _ = parser.parse_known_args()

FR3_STAGE_PATH = "/FR3"
FR3_USD_PATH = "/Isaac/Robots/FrankaRobotics/FrankaFR3/fr3.usd"
BACKGROUND_STAGE_PATH = "/background"
BACKGROUND_USD_PATH = "/Isaac/Environments/Simple_Room/simple_room.usd"

CONFIG = {"renderer": "RealTimePathTracing", "headless": False}

simulation_app = SimulationApp(CONFIG)
import carb
import isaacsim.core.experimental.utils.app as app_utils
import isaacsim.core.experimental.utils.stage as stage_utils
import omni
import omni.graph.core as og
import usdrt.Sdf
from isaacsim.core.experimental.utils.prim import get_prim_at_path
from isaacsim.core.rendering_manager import ViewportManager
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.storage.native import get_assets_root_path
from pxr import Gf, UsdGeom

import omni.replicator.core as rep
import omni.syntheticdata._syntheticdata as sd
from isaacsim.sensors.camera import Camera
import isaacsim.core.experimental.utils.transform as transform_utils

app_utils.enable_extension("isaacsim.ros2.bridge")
simulation_app.update()

stage_utils.set_stage_units(meters_per_unit=1.0)
assets_root_path = get_assets_root_path()
if assets_root_path is None:
    carb.log_error("Could not find Isaac Sim assets folder")
    simulation_app.close()
    sys.exit()

ViewportManager.set_camera_view("/OmniverseKit_Persp", eye=np.array([1.2, 1.2, 0.8]), target=np.array([0, 0, 0.5]))
stage_utils.add_reference_to_stage(assets_root_path + BACKGROUND_USD_PATH, BACKGROUND_STAGE_PATH)
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, FR3_STAGE_PATH)
robot = get_prim_at_path(FR3_STAGE_PATH)

xform_api = UsdGeom.XformCommonAPI(robot)
xform_api.SetTranslate(Gf.Vec3d(0, -0.64, 0))
xform_api.SetRotate((0, 0, 90), UsdGeom.XformCommonAPI.RotationOrderXYZ)

simulation_app.update()

# Creating the Action Graph for ROS 2 Bridge (Joint Control)
try:
    og.Controller.edit(
        {"graph_path": "/ActionGraph", "evaluator_name": "execution"},
        {
            og.Controller.Keys.CREATE_NODES: [
                ("OnPlaybackTick", "omni.graph.action.OnPlaybackTick"),
                ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                ("ReadJointState", "isaacsim.sensors.physics.IsaacReadJointState"),
                ("Context", "isaacsim.ros2.bridge.ROS2Context"),
                ("PublishJointState", "isaacsim.ros2.bridge.ROS2PublishJointState"),
                ("SubscribeJointState", "isaacsim.ros2.bridge.ROS2SubscribeJointState"),
                ("ArticulationController", "isaacsim.core.nodes.IsaacArticulationController"),
                ("PublishClock", "isaacsim.ros2.bridge.ROS2PublishClock"),
            ],
            og.Controller.Keys.CONNECT: [
                ("OnPlaybackTick.outputs:tick", "ReadJointState.inputs:execIn"),
                ("ReadJointState.outputs:execOut", "PublishJointState.inputs:execIn"),
                ("ReadJointState.outputs:jointNames", "PublishJointState.inputs:jointNames"),
                ("ReadJointState.outputs:jointPositions", "PublishJointState.inputs:jointPositions"),
                ("ReadJointState.outputs:jointVelocities", "PublishJointState.inputs:jointVelocities"),
                ("ReadJointState.outputs:jointEfforts", "PublishJointState.inputs:jointEfforts"),
                ("ReadJointState.outputs:jointDofTypes", "PublishJointState.inputs:jointDofTypes"),
                ("ReadJointState.outputs:stageMetersPerUnit", "PublishJointState.inputs:stageMetersPerUnit"),
                ("ReadJointState.outputs:sensorTime", "PublishJointState.inputs:sensorTime"),
                ("OnPlaybackTick.outputs:tick", "SubscribeJointState.inputs:execIn"),
                ("OnPlaybackTick.outputs:tick", "PublishClock.inputs:execIn"),
                ("OnPlaybackTick.outputs:tick", "ArticulationController.inputs:execIn"),
                ("Context.outputs:context", "PublishJointState.inputs:context"),
                ("Context.outputs:context", "SubscribeJointState.inputs:context"),
                ("Context.outputs:context", "PublishClock.inputs:context"),
                ("ReadSimTime.outputs:simulationTime", "PublishClock.inputs:timeStamp"),
                ("SubscribeJointState.outputs:jointNames", "ArticulationController.inputs:jointNames"),
                ("SubscribeJointState.outputs:positionCommand", "ArticulationController.inputs:positionCommand"),
                ("SubscribeJointState.outputs:velocityCommand", "ArticulationController.inputs:velocityCommand"),
                ("SubscribeJointState.outputs:effortCommand", "ArticulationController.inputs:effortCommand"),
            ],
            og.Controller.Keys.SET_VALUES: [
                ("ArticulationController.inputs:robotPath", FR3_STAGE_PATH),
                ("ReadJointState.inputs:prim", [usdrt.Sdf.Path(FR3_STAGE_PATH)]),
                ("PublishJointState.inputs:topicName", "isaac_joint_states"),
                ("SubscribeJointState.inputs:topicName", "isaac_joint_commands"),
            ],
        },
    )
except Exception as e:
    print(e)


###################################################################
# Adding the Wrist Camera
###################################################################

# Create a camera attached to the hand
camera_path = FR3_STAGE_PATH + "/fr3_hand/wrist_camera"

# We offset it so it points outward from the gripper
camera = Camera(
    prim_path=camera_path,
    position=np.array([0.05, 0.0, 0.0]), 
    frequency=30,
    resolution=(640, 480),
    orientation=transform_utils.euler_angles_to_quaternion(np.array([0, -90, 0]), degrees=True).numpy()
)
camera.initialize()
simulation_app.update()

def publish_rgb(camera: Camera, freq):
    render_product = camera._render_product_path
    step_size = int(60 / freq)
    topic_name = "wrist_camera/rgb"
    
    rv = omni.syntheticdata.SyntheticData.convert_sensor_type_to_rendervar(sd.SensorType.Rgb.name)
    writer = rep.writers.get(rv + "ROS2PublishImage")
    writer.initialize(frameId="wrist_camera", topicName=topic_name)
    writer.attach([render_product])

    gate_path = omni.syntheticdata.SyntheticData._get_node_path(rv + "IsaacSimulationGate", render_product)
    og.Controller.attribute(gate_path + ".inputs:step").set(step_size)

publish_rgb(camera, 30)

###################################################################

simulation_app.update()
SimulationManager.setup_simulation(dt=1.0 / 60.0, device="cpu")
app_utils.play()
simulation_app.update()

frame_count = 0
while simulation_app.is_running():
    simulation_app.update()
    frame_count += 1
    if args.test and frame_count >= 10:
        break

app_utils.stop()
simulation_app.close()
