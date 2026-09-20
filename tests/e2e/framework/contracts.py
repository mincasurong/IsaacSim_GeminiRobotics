"""Authoritative specifications and interface contracts for the Isaac Sim + Gemini Robotics project."""
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# 1. Feature Inventory Specifications
FEATURES = {
    1: {"name": "Standalone Kitchen Sim Script", "milestone": "M1", "file": "isaacsim_scripts/kitchen_three_robot.py"},
    2: {"name": "Procedural Flat Dishes", "milestone": "M1", "mass": 0.18, "friction": 0.7},
    3: {"name": "Procedural Cylindrical Cups", "milestone": "M1", "mass": 0.15, "friction": 0.7},
    4: {"name": "Procedural Oversized Long Bar", "milestone": "M1", "span_min": 0.44, "span_max": 0.55},
    5: {"name": "Synthetic Overhead RGB-D Camera", "milestone": "M1", "topics": ["/overhead_camera/rgb", "/overhead_camera/depth", "/overhead_camera/camera_info"]},
    6: {"name": "Dynamic /tf Tree Broadcasting", "milestone": "M1", "topic": "/tf", "frames": ["Dish1", "Dish2", "Dish3", "Cup1", "Cup2", "Cup3", "LongBar1"]},
    7: {"name": "Single-Arm Dish Manipulation", "milestone": "M2", "target": "Dish", "approach_z": 0.08, "grasp_z": 0.02},
    8: {"name": "Single-Arm Cup Manipulation", "milestone": "M2", "target": "Cup", "approach_z": 0.12, "grasp_z": 0.05},
    9: {"name": "Kitchen Table Clearing/Organizing", "milestone": "M2", "staging_zone": "central_table"},
    10: {"name": "Dual-Arm Kinematic Coordination", "milestone": "M3", "robots": ["FR3_1", "FR3_2"], "sync_mode": "rigid_body"},
    11: {"name": "Synchronized Approach & Contact Closure", "milestone": "M3", "phases": 11},
    12: {"name": "Coupled Cartesian Transport", "milestone": "M3", "max_distance_drift": 0.005},
    13: {"name": "Synchronized Release & Compliance", "milestone": "M3", "outward_retreat": True},
    14: {"name": "Collaborative Telemetry Publishing", "milestone": "M3", "topic": "/multi_robot/robot_metrics"},
    15: {"name": "Fix Utility Function Bug", "milestone": "M4", "file": "wsl_ws/src/isaac_ros2_control/isaac_ros2_control/gemini_utils.py", "function": "resolve_object_key"},
    16: {"name": "Affordance Reasoning Rules", "milestone": "M4", "file": "wsl_ws/src/isaac_ros2_control/isaac_ros2_control/gemini_prompts.py"},
    17: {"name": "Dual-Arm Action Tool Schemas", "milestone": "M4", "file": "wsl_ws/src/isaac_ros2_control/isaac_ros2_control/gemini_tools.py", "tool": "dual_arm_transport"},
    18: {"name": "Kitchen Multi-Agent Prompts", "milestone": "M4", "file": "wsl_ws/src/isaac_ros2_control/isaac_ros2_control/gemini_prompts.py"},
    19: {"name": "SceneMap Kitchen Object Tokens", "milestone": "M5", "file": "gemini_web_gui/src/components/SceneMap.tsx"},
    20: {"name": "Dual-Arm Linkage Visualization", "milestone": "M5", "file": "gemini_web_gui/src/components/AgentWorkflowGraph.tsx"},
    21: {"name": "Kitchen Quick-Prompt Chips", "milestone": "M5", "file": "gemini_web_gui/src/App.tsx"},
    22: {"name": "Clean TypeScript Build", "milestone": "M5", "directory": "gemini_web_gui"}
}

# 2. Physics & Geometry Bounds
WORKSPACE_BOUNDS = {
    "central_table": {
        "x": (-0.25, 0.25),
        "y": (-0.25, 0.25),
        "z": 0.20
    },
    "table_surface_z": 0.20,
    "hover_height": 0.10
}

# Franka FR3 7-DOF Joint Limits (radians)
FR3_JOINT_LIMITS = [
    (-2.8973, 2.8973),  # Joint 1
    (-1.7628, 1.7628),  # Joint 2
    (-2.8973, 2.8973),  # Joint 3
    (-3.0718, -0.0698), # Joint 4
    (-2.8973, 2.8973),  # Joint 5
    (-0.0175, 3.7525),  # Joint 6
    (-2.8973, 2.8973),  # Joint 7
]

# Gripper Limits (meters per finger)
FR3_GRIPPER_LIMITS = (0.0, 0.04)

# 3. ROS 2 Interface Contracts
ROS2_TOPICS = {
    "action_cmd": "/gemini/action",
    "action_res": "/gemini/action_result",
    "telemetry": "/multi_robot/robot_metrics",
    "tf": "/tf",
    "camera_rgb": "/overhead_camera/rgb",
    "camera_depth": "/overhead_camera/depth",
    "camera_info": "/overhead_camera/camera_info"
}

# Action Command Schema
ACTION_COMMAND_SCHEMA = {
    "type": "object",
    "required": ["action"],
    "properties": {
        "action": {"type": "string", "enum": ["pick", "place", "place_relative", "dual_carry", "go_home"]},
        "robot": {"type": "string", "enum": ["FR3_1", "FR3_2", "FR3_3"]},
        "robots": {"type": "array", "items": {"type": "string", "enum": ["FR3_1", "FR3_2", "FR3_3"]}},
        "target": {"type": "string"},
        "object": {"type": "string"},
        "destination": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
        "sync_mode": {"type": "string", "enum": ["rigid_body", "leader_follower"]}
    }
}

# Action Result Schema
ACTION_RESULT_SCHEMA = {
    "type": "object",
    "required": ["robot", "action", "status"],
    "properties": {
        "robot": {"type": "string"},
        "action": {"type": "string"},
        "status": {"type": "string", "enum": ["SUCCESS", "FAILURE", "IN_PROGRESS"]},
        "message": {"type": "string"}
    }
}

# Telemetry Schema
TELEMETRY_SCHEMA = {
    "type": "object",
    "required": ["robots", "collaborative_active"],
    "properties": {
        "robots": {"type": "object"},
        "center_occupied_by": {"type": ["string", "null"]},
        "collaborative_active": {"type": "boolean"},
        "collaborative_pair": {"type": ["array", "null"], "items": {"type": "string"}},
        "collaborative_object": {"type": ["string", "null"]}
    }
}
