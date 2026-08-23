# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import argparse
import sys
import numpy as np
from isaacsim import SimulationApp

parser = argparse.ArgumentParser()
parser.add_argument("--test", default=False, action="store_true", help="Run in test mode")
parser.add_argument("--headless", default=False, action="store_true", help="Run in headless mode")
parser.add_argument("--mobile-base", default="carter_v1", help="Mobile base type: nova_carter, carter_v1")
parser.add_argument("--environment", default="simple_room", help="Environment type: warehouse, office, simple_room, hospital")
args, unknown_args = parser.parse_known_args()

# Filter sys.argv to avoid SimulationApp errors
sys.argv = [sys.argv[0]] + unknown_args

MOBILE_BASES = {
    "nova_carter": {
        "usd_path": "/Isaac/Robots/NVIDIA/NovaCarter/nova_carter.usd",
        "mount_height": 0.554,
        "chassis_prim": "/World/Robot/chassis_link",
        "wheel_joints": ["joint_wheel_left", "joint_wheel_right"],
        "wheel_radius": 0.14,
        "wheel_distance": 0.499
    },
    "carter_v1": {
        "usd_path": "/Isaac/Robots/NVIDIA/Carter/carter_v1.usd",
        "mount_height": 0.412,
        "chassis_prim": "/World/Robot/chassis_link",
        "wheel_joints": ["left_wheel", "right_wheel"],
        "wheel_radius": 0.24,
        "wheel_distance": 0.628
    }
}

base_info = MOBILE_BASES.get(args.mobile_base, MOBILE_BASES["nova_carter"])

import os
SCENE_USD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "industrial_mobile_manipulator_scene.usd")
ROBOT_STAGE_PATH = base_info["chassis_prim"]

CONFIG = {"renderer": "RayTracedLighting", "headless": args.headless}

simulation_app = SimulationApp(CONFIG)

import carb
import isaacsim.core.experimental.utils.app as app_utils
import isaacsim.core.experimental.utils.stage as stage_utils
import omni.graph.core as og
import usdrt.Sdf
from isaacsim.core.experimental.utils.prim import get_prim_at_path
from isaacsim.core.rendering_manager import ViewportManager
from isaacsim.core.simulation_manager import SimulationManager
import omni.usd

print("Enabling ROS2 bridge extension...")
app_utils.enable_extension("isaacsim.ros2.bridge")
simulation_app.update()

# Load the assembled USD scene
print(f"Loading USD scene from: {SCENE_USD_PATH}")
omni.usd.get_context().open_stage(SCENE_USD_PATH, None)

# Wait for stage to load fully
simulation_app.update()
simulation_app.update()

from pxr import Gf
from isaacsim.core.experimental.utils.stage import is_stage_loading
while is_stage_loading():
    simulation_app.update()
print("Scene loaded completely.")

# Raise tables to ensure relative block Z-height sits at 0.2m relative to the arm base
stage = omni.usd.get_context().get_stage()
print("[SCENE] Setting table translation heights (positioning on floor)...")
for path, val in [("/World/Table_1", Gf.Vec3d(1.8, 0.0, 0.0)), ("/World/Table_2", Gf.Vec3d(0.0, 1.8, 0.0))]:
    prim = stage.GetPrimAtPath(path)
    if prim.IsValid():
        translate_attr = prim.GetAttribute("xformOp:translate")
        if translate_attr.IsValid():
            translate_attr.Set(val)

# Set up the camera view to overlook the workspace
ViewportManager.set_camera_view("/OmniverseKit_Persp", eye=np.array([3.5, 3.5, 2.5]), target=np.array([0, 0, 0.7]))
simulation_app.update()

# Creating the Action Graph for ROS 2 Bridge (Mobile Manipulator base and arm)
print("Creating ROS2 Action Graph...")
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
                
                # Odometry nodes
                ("ComputeOdom", "isaacsim.core.nodes.IsaacComputeOdometry"),
                ("PublishOdom", "isaacsim.ros2.bridge.ROS2PublishOdometry"),
                
                # Base Twist control nodes
                ("SubscribeTwist", "isaacsim.ros2.bridge.ROS2SubscribeTwist"),
                ("BreakLinVel", "omni.graph.nodes.BreakVector3"),
                ("BreakAngVel", "omni.graph.nodes.BreakVector3"),
                ("DiffController", "isaacsim.robot.wheeled_robots.DifferentialController"),
                ("ArtControllerBase", "isaacsim.core.nodes.IsaacArticulationController"),
                
                # Arm Joint State pub nodes
                ("ReadJointState", "isaacsim.sensors.physics.IsaacReadJointState"),
                ("PublishJointState", "isaacsim.ros2.bridge.ROS2PublishJointState"),
                
                # Arm Joint Command sub nodes
                ("SubscribeJointState", "isaacsim.ros2.bridge.ROS2SubscribeJointState"),
                ("ArtControllerArm", "isaacsim.core.nodes.IsaacArticulationController"),
            ],
            og.Controller.Keys.CONNECT: [
                # Clock connection
                ("OnPlaybackTick.outputs:tick", "PublishClock.inputs:execIn"),
                ("Context.outputs:context", "PublishClock.inputs:context"),
                ("ReadSimTime.outputs:simulationTime", "PublishClock.inputs:timeStamp"),
                
                # TF connection
                ("OnPlaybackTick.outputs:tick", "PublishTF.inputs:execIn"),
                ("Context.outputs:context", "PublishTF.inputs:context"),
                ("ReadSimTime.outputs:simulationTime", "PublishTF.inputs:timeStamp"),
                
                # Odom connections
                ("OnPlaybackTick.outputs:tick", "ComputeOdom.inputs:execIn"),
                ("ComputeOdom.outputs:execOut", "PublishOdom.inputs:execIn"),
                ("Context.outputs:context", "PublishOdom.inputs:context"),
                ("ReadSimTime.outputs:simulationTime", "PublishOdom.inputs:timeStamp"),
                ("ComputeOdom.outputs:angularVelocity", "PublishOdom.inputs:angularVelocity"),
                ("ComputeOdom.outputs:linearVelocity", "PublishOdom.inputs:linearVelocity"),
                ("ComputeOdom.outputs:orientation", "PublishOdom.inputs:orientation"),
                ("ComputeOdom.outputs:position", "PublishOdom.inputs:position"),
                
                # Twist Subscriber to base motor controller
                ("OnPlaybackTick.outputs:tick", "SubscribeTwist.inputs:execIn"),
                ("Context.outputs:context", "SubscribeTwist.inputs:context"),
                ("SubscribeTwist.outputs:execOut", "DiffController.inputs:execIn"),
                ("SubscribeTwist.outputs:linearVelocity", "BreakLinVel.inputs:tuple"),
                ("BreakLinVel.outputs:x", "DiffController.inputs:linearVelocity"),
                ("SubscribeTwist.outputs:angularVelocity", "BreakAngVel.inputs:tuple"),
                ("BreakAngVel.outputs:z", "DiffController.inputs:angularVelocity"),
                
                ("OnPlaybackTick.outputs:tick", "ArtControllerBase.inputs:execIn"),
                ("DiffController.outputs:velocityCommand", "ArtControllerBase.inputs:velocityCommand"),
                
                # Joint State Publisher connections
                ("OnPlaybackTick.outputs:tick", "ReadJointState.inputs:execIn"),
                ("ReadJointState.outputs:execOut", "PublishJointState.inputs:execIn"),
                ("Context.outputs:context", "PublishJointState.inputs:context"),
                ("ReadJointState.outputs:jointNames", "PublishJointState.inputs:jointNames"),
                ("ReadJointState.outputs:jointPositions", "PublishJointState.inputs:jointPositions"),
                ("ReadJointState.outputs:jointVelocities", "PublishJointState.inputs:jointVelocities"),
                ("ReadJointState.outputs:jointEfforts", "PublishJointState.inputs:jointEfforts"),
                ("ReadJointState.outputs:jointDofTypes", "PublishJointState.inputs:jointDofTypes"),
                ("ReadJointState.outputs:stageMetersPerUnit", "PublishJointState.inputs:stageMetersPerUnit"),
                ("ReadJointState.outputs:sensorTime", "PublishJointState.inputs:sensorTime"),
                
                # Joint Command Subscriber connections
                ("OnPlaybackTick.outputs:tick", "SubscribeJointState.inputs:execIn"),
                ("Context.outputs:context", "SubscribeJointState.inputs:context"),
                ("OnPlaybackTick.outputs:tick", "ArtControllerArm.inputs:execIn"),
                ("SubscribeJointState.outputs:jointNames", "ArtControllerArm.inputs:jointNames"),
                ("SubscribeJointState.outputs:positionCommand", "ArtControllerArm.inputs:positionCommand"),
                ("SubscribeJointState.outputs:velocityCommand", "ArtControllerArm.inputs:velocityCommand"),
                ("SubscribeJointState.outputs:effortCommand", "ArtControllerArm.inputs:effortCommand"),
            ],
            og.Controller.Keys.SET_VALUES: [
                # TF targets
                ("PublishTF.inputs:topicName", "/tf"),
                ("PublishTF.inputs:targetPrims", [
                    usdrt.Sdf.Path("/World"),
                    usdrt.Sdf.Path("/World/Robot"),
                    usdrt.Sdf.Path("/World/Robot/chassis_link"),
                    usdrt.Sdf.Path("/World/Robot/chassis_link/fr3/fr3_link0"),
                    usdrt.Sdf.Path("/World/Block1"),
                    usdrt.Sdf.Path("/World/Block2"),
                    usdrt.Sdf.Path("/World/Block3"),
                    usdrt.Sdf.Path("/World/Block4"),
                ]),
                
                # Odom targets
                ("ComputeOdom.inputs:chassisPrim", [usdrt.Sdf.Path("/World/Robot/chassis_link")]),
                ("PublishOdom.inputs:topicName", "/odom"),
                ("PublishOdom.inputs:odomFrameId", "odom"),
                ("PublishOdom.inputs:chassisFrameId", "base_link"),
                
                # Twist Subscriber topic
                ("SubscribeTwist.inputs:topicName", "/cmd_vel"),
                
                # Diff controller settings
                ("DiffController.inputs:wheelRadius", base_info["wheel_radius"]),
                ("DiffController.inputs:wheelDistance", base_info["wheel_distance"]),
                
                # Articulation Controller settings for mobile base
                ("ArtControllerBase.inputs:robotPath", ROBOT_STAGE_PATH),
                ("ArtControllerBase.inputs:jointNames", base_info["wheel_joints"]),
                
                # Joint State Publisher settings (points to full robot)
                ("ReadJointState.inputs:prim", [usdrt.Sdf.Path(ROBOT_STAGE_PATH)]),
                ("PublishJointState.inputs:topicName", "/joint_states"),
                
                # Joint Command Subscriber settings
                ("SubscribeJointState.inputs:topicName", "/joint_commands"),
                ("ArtControllerArm.inputs:robotPath", ROBOT_STAGE_PATH),
            ]
        }
    )
    print("Action Graph successfully configured.")
except Exception as graph_err:
    print(f"Error creating Action Graph: {graph_err}")
    simulation_app.close()
    sys.exit(1)

simulation_app.update()

# Set up simulation context and start playing
SimulationManager.setup_simulation(dt=1.0 / 60.0, device="cpu")
app_utils.play()
simulation_app.update()

# Robot initialization and reset setup
try:
    from isaacsim.core.prims import Articulation, RigidPrim
    robot_art = Articulation(ROBOT_STAGE_PATH)
    robot_art.initialize()
    
    # Establish initial pose to prevent physics resetting to default
    robot_art.set_world_poses(
        positions=np.array([[0.0, 0.0, 0.15]]),
        orientations=np.array([[1.0, 0.0, 0.0, 0.0]])
    )
    
    # Map joint configurations dynamically
    dof_names = list(robot_art.dof_names)
    print(f"Resolved DOF names: {dof_names}")
    
    arm_joint_positions = {
        "fr3_joint1": 3.14159,
        "fr3_joint2": 0.0,
        "fr3_joint3": 0.0,
        "fr3_joint4": -1.57,
        "fr3_joint5": 0.0,
        "fr3_joint6": 1.57,
        "fr3_joint7": 0.785,
        "fr3_finger_joint1": 0.04,
        "fr3_finger_joint2": 0.04,
    }
    
    q_home = np.zeros(robot_art.num_dof)
    for name, val in arm_joint_positions.items():
        if name in dof_names:
            idx = dof_names.index(name)
            q_home[idx] = val
            
    robot_art.set_joint_positions(q_home)
    
    # Initialize pick blocks
    blocks = []
    block_initial_positions = [
        [1.6, 0.15, 0.735],
        [1.6, -0.15, 0.735],
        [1.7, 0.15, 0.735],
        [1.7, -0.15, 0.735]
    ]
    for i in range(4):
        block_prim = RigidPrim(f"/World/Block{i+1}")
        block_prim.initialize()
        blocks.append(block_prim)
        
    # Set up ROS2 reset interfaces
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Empty
    from std_srvs.srv import Trigger
    from geometry_msgs.msg import PoseArray, Pose
    
    if not rclpy.ok():
        rclpy.init()
        
    reset_node = Node("mobile_manipulator_env_node")
    reset_pub = reset_node.create_publisher(Empty, "/reset_simulation", 10)
    block_pub = reset_node.create_publisher(PoseArray, "/target_blocks", 10)
    
    def publish_blocks():
        msg = PoseArray()
        msg.header.frame_id = "world"
        msg.header.stamp = reset_node.get_clock().now().to_msg()
        for b in blocks:
            pos, quat = b.get_world_poses()
            p = Pose()
            p.position.x = float(pos[0][0])
            p.position.y = float(pos[0][1])
            p.position.z = float(pos[0][2])
            p.orientation.w = float(quat[0][0])
            p.orientation.x = float(quat[0][1])
            p.orientation.y = float(quat[0][2])
            p.orientation.z = float(quat[0][3])
            msg.poses.append(p)
        block_pub.publish(msg)
        
    block_timer = reset_node.create_timer(0.1, publish_blocks)
    
    def reset_simulation(publish_to_ros=True):
        print("[RESET] Re-initializing robot and block states...")
        try:
            # Reset robot base joints + velocities
            robot_art.set_joint_positions(q_home)
            robot_art.set_joint_velocities(np.zeros(robot_art.num_dof))
            robot_art.set_world_poses(
                positions=np.array([[0.0, 0.0, 0.15]]),
                orientations=np.array([[1.0, 0.0, 0.0, 0.0]])
            )
            # Reset pick blocks
            for idx, bp in enumerate(blocks):
                bp.set_world_poses(
                    positions=np.array([block_initial_positions[idx]]),
                    orientations=np.array([[1.0, 0.0, 0.0, 0.0]])
                )
                bp.set_linear_velocities(np.zeros((1, 3)))
                bp.set_angular_velocities(np.zeros((1, 3)))
            print("[RESET] Successfully completed.")
            
            if publish_to_ros:
                reset_pub.publish(Empty())
        except Exception as reset_err:
            print(f"[RESET] Error during reset: {reset_err}")
            
    # ROS2 Reset Subscriptions
    def ros_reset_callback(msg):
        print("[RESET] Received reset empty topic request.")
        reset_simulation(publish_to_ros=False)
        
    reset_sub = reset_node.create_subscription(Empty, "/reset_simulation", ros_reset_callback, 10)
    
    # ROS2 Reset Service callback
    def ros_reset_service_callback(request, response):
        print("[RESET] Received reset service call.")
        reset_simulation(publish_to_ros=True)
        response.success = True
        response.message = "Mobile manipulator environment successfully reset"
        return response
        
    reset_srv = reset_node.create_service(Trigger, "/reset_simulation", ros_reset_service_callback)
    
    # Keyboard Reset Hook
    import omni.appwindow
    import carb.input
    
    def on_keyboard_event(event, *args, **kwargs):
        if event.type == carb.input.KeyboardEventType.KEY_PRESS:
            if event.input.name in ["R", "I"]:
                print(f"[KEYBOARD] Reset triggered by pressing key '{event.input.name}'")
                reset_simulation(publish_to_ros=True)
        return True
        
    appwindow = omni.appwindow.get_default_app_window()
    input_interface = carb.input.acquire_input_interface()
    keyboard = appwindow.get_keyboard()
    sub_keyboard = input_interface.subscribe_to_keyboard_events(keyboard, on_keyboard_event)
    
    # UI Control Panel
    try:
        if not args.headless:
            import omni.ui as ui
            control_window = ui.Window("Mobile Manipulator Control", width=300, height=140)
            with control_window.frame:
                with ui.VStack(spacing=10):
                    ui.Spacer(height=2)
                    ui.Label("Mobile Manipulator Factory Simulation", alignment=ui.Alignment.CENTER)
                    ui.Label("Press 'R' / 'I' keys to trigger reset", alignment=ui.Alignment.CENTER)
                    init_btn = ui.Button("Reset Robot & Scene", height=35)
                    init_btn.set_clicked_fn(lambda: reset_simulation(publish_to_ros=True))
                    ui.Spacer(height=2)
            print("[UI] Simulation panel created successfully.")
    except Exception as ui_err:
        print(f"[UI] Warning: Could not initialize panel UI: {ui_err}")

except Exception as init_err:
    print(f"Error setting up simulation initial states: {init_err}")
    reset_node = None

# Main loop
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
