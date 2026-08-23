# SPDX-FileCopyrightText: Copyright (c) 2020-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import argparse
import sys
import os

# Locate kinematics module dynamically relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))
wsl_ws_path = None
curr = script_dir
for _ in range(6):
    candidate = os.path.join(curr, "wsl_ws", "src", "isaac_ros2_control", "isaac_ros2_control")
    if os.path.isdir(candidate):
        wsl_ws_path = candidate
        break
    parent = os.path.dirname(curr)
    if parent == curr:
        break
    curr = parent

if wsl_ws_path:
    if wsl_ws_path not in sys.path:
        sys.path.append(wsl_ws_path)

try:
    import kinematics
    HAS_KINEMATICS = True
except Exception as e:
    print(f"[RANDOMIZATION] Warning: Failed to import kinematics module: {e}")
    HAS_KINEMATICS = False

import numpy as np
from isaacsim import SimulationApp

parser = argparse.ArgumentParser()
parser.add_argument("--test", default=False, action="store_true", help="Run in test mode")
parser.add_argument("--headless", default=False, action="store_true", help="Run in headless mode")
args, _ = parser.parse_known_args()

FR3_1_STAGE_PATH = "/FR3_1"
FR3_2_STAGE_PATH = "/FR3_2"
FR3_USD_PATH = "/Isaac/Robots/FrankaRobotics/FrankaFR3/fr3.usd"
BACKGROUND_STAGE_PATH = "/background"
BACKGROUND_USD_PATH = "/Isaac/Environments/Simple_Room/simple_room.usd"

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
from pxr import Gf, UsdGeom, UsdPhysics, Usd
import omni.usd

app_utils.enable_extension("isaacsim.ros2.bridge")
simulation_app.update()

stage_utils.set_stage_units(meters_per_unit=1.0)
assets_root_path = get_assets_root_path()
if assets_root_path is None:
    carb.log_error("Could not find Isaac Sim assets folder")
    simulation_app.close()
    sys.exit()

ViewportManager.set_camera_view("/OmniverseKit_Persp", eye=np.array([1.5, 0.0, 1.2]), target=np.array([0.4, 0.0, 0.5]))
stage_utils.add_reference_to_stage(assets_root_path + BACKGROUND_USD_PATH, BACKGROUND_STAGE_PATH)

# Add Robot 1
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, FR3_1_STAGE_PATH)
robot1 = get_prim_at_path(FR3_1_STAGE_PATH)
xform_api1 = UsdGeom.XformCommonAPI(robot1)
xform_api1.SetTranslate(Gf.Vec3d(-0.45, -0.45, 0.0))
xform_api1.SetRotate((0, 0, 45), UsdGeom.XformCommonAPI.RotationOrderXYZ)

# Add Robot 2
stage_utils.add_reference_to_stage(assets_root_path + FR3_USD_PATH, FR3_2_STAGE_PATH)
robot2 = get_prim_at_path(FR3_2_STAGE_PATH)
xform_api2 = UsdGeom.XformCommonAPI(robot2)
xform_api2.SetTranslate(Gf.Vec3d(0.45, 0.45, 0.0))
xform_api2.SetRotate((0, 0, -135), UsdGeom.XformCommonAPI.RotationOrderXYZ)

stage = omni.usd.get_context().get_stage()



simulation_app.update()

# Add wrist cameras
stage = omni.usd.get_context().get_stage()

def add_wrist_camera(robot_path):
    cam_path = f"{robot_path}/fr3_hand/wrist_camera"
    cam_prim = UsdGeom.Camera.Define(stage, cam_path)
    # Set camera facing forward from the hand
    xform_cam = UsdGeom.Xformable(cam_prim)
    xform_cam.ClearXformOpOrder()
    xform_cam.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 0.05))
    xform_cam.AddRotateXYZOp().Set(Gf.Vec3d(180, 0, 0))
    cam_prim.GetFocalLengthAttr().Set(24.0)

add_wrist_camera(FR3_1_STAGE_PATH)
add_wrist_camera(FR3_2_STAGE_PATH)

# Traverse the stage to check for any table prims and ensure they are static colliders so they don't fall
print("[PHYSICS] Checking table prims for correct physics properties...")
background_prim = stage.GetPrimAtPath("/background")
if background_prim:
    for prim in Usd.PrimRange(background_prim):
        path = prim.GetPath().pathString
        if "table" in path.lower():
            print(f"[PHYSICS] Configuring table prim {path} as static collider...")
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                prim.RemoveAPI(UsdPhysics.RigidBodyAPI)
            rb_enabled_attr = prim.GetAttribute("physics:rigidBodyEnabled")
            if rb_enabled_attr.IsValid():
                rb_enabled_attr.Set(False)
            kin_enabled_attr = prim.GetAttribute("physics:kinematicEnabled")
            if kin_enabled_attr.IsValid():
                kin_enabled_attr.Set(False)
            if not prim.HasAPI(UsdPhysics.CollisionAPI):
                UsdPhysics.CollisionAPI.Apply(prim)


def generate_random_positions(side="left"):
    positions = []
    min_dist = 0.14
    
    for _ in range(3):
        for attempt in range(2000):
            # Polar sampling to place blocks further away from base to avoid singularities
            # r ranges from 0.35m to 0.70m for a much larger reachable area
            r = np.random.uniform(0.35, 0.70)
            
            if side == "left":
                # Sample a broad angle in front of the robot (robot at 45 deg)
                theta_world = np.random.uniform(np.radians(0), np.radians(90))
                x_w = -0.45 + r * np.cos(theta_world)
                y_w = -0.45 + r * np.sin(theta_world)
                
                # Keep out of the stack area [0,0]
                if x_w > -0.05 and y_w > -0.05:
                    continue
                    
            else:
                # Sample a broad angle in front of the right robot (robot at -135 deg)
                theta_world = np.random.uniform(np.radians(-180), np.radians(-90))
                x_w = 0.45 + r * np.cos(theta_world)
                y_w = 0.45 + r * np.sin(theta_world)
                
                # Keep out of the stack area [0,0]
                if x_w < 0.05 and y_w < 0.05:
                    continue
            
            # Check overlap
            valid = True
            for pos in positions:
                dist = np.sqrt((x_w - pos[0])**2 + (y_w - pos[1])**2)
                if dist < min_dist:
                    valid = False
                    break
            if valid:
                positions.append((x_w, y_w, 0.0404))
                break
        else:
            print(f"[WARN] Could not find valid non-overlapping position for {side} side after 2000 attempts.")
            
    return positions

# Create blocks
np.random.seed()
block_positions = generate_random_positions("left") + generate_random_positions("right")

block_colors = [
    Gf.Vec3f(0.8, 0.2, 0.2),  # Red
    Gf.Vec3f(0.2, 0.8, 0.2),  # Green
    Gf.Vec3f(0.2, 0.2, 0.8),  # Blue
    Gf.Vec3f(0.8, 0.8, 0.2),  # Yellow
    Gf.Vec3f(0.8, 0.2, 0.8),  # Magenta
    Gf.Vec3f(0.2, 0.8, 0.8),  # Cyan
]

for i, pos in enumerate(block_positions):
    block_path = f"/Block{i+1}"
    cube = UsdGeom.Cube.Define(stage, block_path)
    cube.GetSizeAttr().Set(1.0)
    xform_cube = UsdGeom.Xformable(cube.GetPrim())
    xform_cube.ClearXformOpOrder()
    xform_cube.AddTranslateOp().Set(Gf.Vec3d(*pos))
    
    theta_deg = np.random.uniform(0, 360)
    xform_cube.AddRotateXYZOp().Set(Gf.Vec3d(0.0, 0.0, theta_deg))
    
    xform_cube.AddScaleOp().Set(Gf.Vec3f(0.06, 0.06, 0.06))  # 6cm cube
    
    # Set unique display color for the block
    cube.CreateDisplayColorAttr().Set([block_colors[i]])
    
    UsdPhysics.RigidBodyAPI.Apply(cube.GetPrim())
    UsdPhysics.CollisionAPI.Apply(cube.GetPrim())

simulation_app.update()

# Creating the Action Graph for ROS 2 Bridge
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
                
                # Robot 1 nodes
                ("ReadJointState1", "isaacsim.sensors.physics.IsaacReadJointState"),
                ("PublishJointState1", "isaacsim.ros2.bridge.ROS2PublishJointState"),
                ("SubscribeJointState1", "isaacsim.ros2.bridge.ROS2SubscribeJointState"),
                ("ArticulationController1", "isaacsim.core.nodes.IsaacArticulationController"),
                
                # Robot 2 nodes
                ("ReadJointState2", "isaacsim.sensors.physics.IsaacReadJointState"),
                ("PublishJointState2", "isaacsim.ros2.bridge.ROS2PublishJointState"),
                ("SubscribeJointState2", "isaacsim.ros2.bridge.ROS2SubscribeJointState"),
                ("ArticulationController2", "isaacsim.core.nodes.IsaacArticulationController"),
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
            ],
            og.Controller.Keys.SET_VALUES: [
                ("PublishTF.inputs:topicName", "/tf"),
                ("PublishTF.inputs:targetPrims", [
                    usdrt.Sdf.Path(FR3_1_STAGE_PATH),
                    usdrt.Sdf.Path(f"{FR3_1_STAGE_PATH}/fr3_link0"),
                    usdrt.Sdf.Path(FR3_2_STAGE_PATH),
                    usdrt.Sdf.Path(f"{FR3_2_STAGE_PATH}/fr3_link0"),
                    usdrt.Sdf.Path("/Block1"), usdrt.Sdf.Path("/Block2"), usdrt.Sdf.Path("/Block3"),
                    usdrt.Sdf.Path("/Block4"), usdrt.Sdf.Path("/Block5"), usdrt.Sdf.Path("/Block6"),
                ]),
                
                # Robot 1 config
                ("ArticulationController1.inputs:robotPath", FR3_1_STAGE_PATH),
                ("ReadJointState1.inputs:prim", [usdrt.Sdf.Path(FR3_1_STAGE_PATH)]),
                ("PublishJointState1.inputs:topicName", "/fr3_1/joint_states"),
                ("SubscribeJointState1.inputs:topicName", "/fr3_1/joint_commands"),
                
                # Robot 2 config
                ("ArticulationController2.inputs:robotPath", FR3_2_STAGE_PATH),
                ("ReadJointState2.inputs:prim", [usdrt.Sdf.Path(FR3_2_STAGE_PATH)]),
                ("PublishJointState2.inputs:topicName", "/fr3_2/joint_states"),
                ("SubscribeJointState2.inputs:topicName", "/fr3_2/joint_commands"),
            ],
        },
    )
except Exception as e:
    print(e)

simulation_app.update()
SimulationManager.setup_simulation(dt=1.0 / 120.0, device="cpu") # faster dt for faster pick/place physics stability
app_utils.play()
simulation_app.update()

try:
    from isaacsim.core.prims import Articulation, RigidPrim
    
    robot1_art = Articulation(FR3_1_STAGE_PATH)
    robot1_art.initialize()
    robot1_art.set_world_poses(positions=np.array([[-0.45, -0.45, 0.0]]), orientations=np.array([[0.92388, 0.0, 0.0, 0.38268]]))
    
    robot2_art = Articulation(FR3_2_STAGE_PATH)
    robot2_art.initialize()
    robot2_art.set_world_poses(positions=np.array([[0.45, 0.45, 0.0]]), orientations=np.array([[0.38268, 0.0, 0.0, -0.92388]]))
    
    q_home = [0.0, 0.0, 0.0, -1.57, 0.0, 1.57, 0.785, 0.04, 0.04]
    robot1_art.set_joint_positions(np.array(q_home))
    robot2_art.set_joint_positions(np.array(q_home))
    
    blocks = []
    for i in range(6):
        block_prim = RigidPrim(f"/Block{i+1}")
        block_prim.initialize()
        blocks.append(block_prim)

    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Empty
    from std_srvs.srv import Trigger

    if not rclpy.ok():
        rclpy.init()

    reset_node = Node('isaac_reset_node')
    reset_pub = reset_node.create_publisher(Empty, '/reset_simulation', 10)

    def reset_simulation(publish_to_ros=True):
        print("[RESET] Resetting robot and blocks to initial poses...")
        try:
            # Generate new randomized positions for the blocks on reset
            new_block_positions = generate_random_positions("left") + generate_random_positions("right")
            
            robot1_art.set_joint_positions(np.array(q_home))
            robot1_art.set_joint_velocities(np.zeros(robot1_art.num_dof))
            robot1_art.set_world_poses(positions=np.array([[-0.45, -0.45, 0.0]]), orientations=np.array([[0.92388, 0.0, 0.0, 0.38268]]))
            
            robot2_art.set_joint_positions(np.array(q_home))
            robot2_art.set_joint_velocities(np.zeros(robot2_art.num_dof))
            robot2_art.set_world_poses(positions=np.array([[0.45, 0.45, 0.0]]), orientations=np.array([[0.38268, 0.0, 0.0, -0.92388]]))
            
            for i, block_prim in enumerate(blocks):
                # Randomize yaw rotation
                theta = np.random.uniform(0, 2 * np.pi)
                qw = np.cos(theta / 2.0)
                qz = np.sin(theta / 2.0)
                
                block_prim.set_world_poses(
                    positions=np.array([[new_block_positions[i][0], new_block_positions[i][1], 0.0404]]),
                    orientations=np.array([[qw, 0.0, 0.0, qz]])
                )
                block_prim.set_linear_velocities(np.zeros((1, 3)))
                block_prim.set_angular_velocities(np.zeros((1, 3)))
                
            if publish_to_ros:
                reset_pub.publish(Empty())
        except Exception as err:
            print(f"[RESET] Error resetting simulation: {err}")

    def ros_reset_callback(msg):
        reset_simulation(publish_to_ros=False)

    reset_sub = reset_node.create_subscription(Empty, '/reset_simulation', ros_reset_callback, 10)

    def ros_reset_service_callback(request, response):
        reset_simulation(publish_to_ros=True)
        response.success = True
        return response

    reset_srv = reset_node.create_service(Trigger, '/reset_simulation', ros_reset_service_callback)

    import omni.appwindow
    import carb.input
    import omni.ui as ui

    def on_keyboard_event(event, *args, **kwargs):
        if event.type == carb.input.KeyboardEventType.KEY_PRESS:
            if event.input.name in ["R", "I"]:
                reset_simulation(publish_to_ros=True)
        return True

    appwindow = omni.appwindow.get_default_app_window()
    input_interface = carb.input.acquire_input_interface()
    keyboard = appwindow.get_keyboard()
    sub_keyboard = input_interface.subscribe_to_keyboard_events(keyboard, on_keyboard_event)

    # Create UI Window
    controls_window = ui.Window("Simulation Controls", width=300, height=100)
    with controls_window.frame:
        with ui.VStack():
            ui.Button("Initialize Pose / Reset Simulation", clicked_fn=lambda: reset_simulation(publish_to_ros=True), height=50)

except Exception as e:
    print(f"Error setting up initial joint positions or reset interfaces: {e}")
    reset_node = None

frame_count = 0
while simulation_app.is_running():
    if reset_node is not None:
        rclpy.spin_once(reset_node, timeout_sec=0.0)
    simulation_app.update()
    frame_count += 1
    if args.test and frame_count >= 10:
        break

app_utils.stop()
simulation_app.close()
