# Hardware Context, OpenUSD Schemas & ROS 2 Interface Definitions (Static IDLs)

> **CONTEXT CACHING INVARIANT NOTICE**:
> This file is strictly static and deterministic. It contains permanent structural definitions, kinematic models, OpenUSD hierarchies, and ROS 2 IDLs for the `IsaacSim_Gemini` physical AI setup. It must NOT be dynamically modified at runtime by execution logs, counters, or timestamps, allowing Google Gemini prefix caching to drop input token costs and latency across multi-turn sessions.

---

## 1. System Platform & Network Topology

```
+--------------------------------------------------------------------------+
| Windows 11 Host                                                          |
|  - NVIDIA Isaac Sim (4.5+ / 6.0) with PhysX 5 GPU Dynamics & Fabric      |
|  - Overhead Synthetic Camera (RGB + Depth) @ 10Hz                        |
|  - React 19 + @xyflow/react Digital Twin Dashboard                       |
|  - FastDDS Unicast Bridge Endpoint                                       |
+------------------------------------+-------------------------------------+
                                     | Dynamic Hyper-V vEthernet (172.x.x.x)
+------------------------------------+-------------------------------------+
| WSL2 (Ubuntu 24.04 LTS)                                                  |
|  - ROS 2 Jazzy Jalisco Core                                              |
|  - FastDDS Unicast Bridge (cyclonedds/fastdds profile configured)        |
|  - multi_robot_controller (50 Hz DLS IK + Workspace Mutex Arbiter)       |
|  - gemini_robotics_node (4-Turn Multi-Agent VLA Engine)                  |
|  - rosbridge_server WebSocket @ ws://localhost:9090                      |
+--------------------------------------------------------------------------+
```

Path Mapping:
- Windows Path: `D:\git\IsaacSim_Gemini\...`
- WSL2 Path: `/mnt/d/git/IsaacSim_Gemini/...`

---

## 2. Multi-Robot Hardware & Kinematic Context

### 2.1 Workspace Coordinates & Layout (World Frame in Meters)
- **Central Assembly Table**:
  - Center: `[0.0, 0.0, 0.30]`
  - Bounding Box: `X in [-0.15, 0.15], Y in [-0.15, 0.15]`
  - Table Surface `Z`: `0.30 m`
- **Block Dimensions & Mass**:
  - Block Height: `0.06 m`
  - Block Width/Length: `0.06 m x 0.06 m`
  - Rigid Body Mass: `0.300 kg`
- **Manipulator Bases & Quadrants**:
  - **`FR3_1`**: Base at `[0.0, -0.45, 0.30]`, Source Table Center at `[0.0, -1.05]`, Quadrant: `bottom`
  - **`FR3_2`**: Base at `[0.3897, 0.225, 0.30]`, Source Table Center at `[0.909, 0.525]`, Quadrant: `top-right`
  - **`FR3_3`**: Base at `[-0.3897, 0.225, 0.30]`, Source Table Center at `[-0.909, 0.525]`, Quadrant: `top-left`

### 2.2 Franka FR3 Kinematic Model (7-DOF)
- **Home Joint Configuration (`rad`)**:
  ```python
  FR3_HOME_CONFIG = [0.0, 0.0, 0.0, -1.5708, 0.0, 1.5708, 0.7854]
  ```
- **Joint Limits (`rad`)**:
  - Joint 1: `[-2.8973, 2.8973]`
  - Joint 2: `[-1.7628, 1.7628]`
  - Joint 3: `[-2.8973, 2.8973]`
  - Joint 4 (Elbow): `[-3.0718, -0.0698]`
  - Joint 5: `[-2.8973, 2.8973]`
  - Joint 6: `[-0.0175, 3.7525]`
  - Joint 7: `[-2.8973, 2.8973]`
- **Joint Origins & DH Homogeneous Offsets**:
  - Joint 1: `xyz = [0.0, 0.0, 0.333], rpy = [0.0, 0.0, 0.0]`
  - Joint 2: `xyz = [0.0, 0.0, 0.0], rpy = [-1.5707963268, 0.0, 0.0]`
  - Joint 3: `xyz = [0.0, -0.316, 0.0], rpy = [1.5707963268, 0.0, 0.0]`
  - Joint 4: `xyz = [0.0825, 0.0, 0.0], rpy = [1.5707963268, 0.0, 0.0]`
  - Joint 5: `xyz = [-0.0825, 0.384, 0.0], rpy = [-1.5707963268, 0.0, 0.0]`
  - Joint 6: `xyz = [0.0, 0.0, 0.0], rpy = [1.5707963268, 0.0, 0.0]`
  - Joint 7: `xyz = [0.088, 0.0, 0.0], rpy = [1.5707963268, 0.0, 0.0]`
- **End-Effector TCP Transforms**:
  - `T_LINK7_TO_LINK8`: translation `[0.0, 0.0, 0.107]`
  - `T_LINK8_TO_HAND`: rotation Z `-0.785398` (-pi/4)
  - `T_HAND_TO_TCP`: translation `[0.0, 0.0, 0.1034]`
- **Motion Control Constraints**:
  - 50 Hz Damped Least Squares (DLS) IK with damping factor `lambda = 0.05`
  - Null-Space projection to center Joint 1 and avoid joint singularities
  - Workspace Mutex: `center_occupied_by` token ensures only one robot arm enters the central assembly zone at any time.

---

## 3. OpenUSD Scene Hierarchy & Schemas

### 3.1 USD Prim Tree
```usd
/World
├── /World/PhysicsScene (UsdPhysics.Scene, PhysXSceneAPI)
├── /World/GroundPlane (UsdGeom.Plane, CollisionAPI)
├── /World/TargetTable (UsdGeom.Xform, center=[0.0, 0.0, 0.30])
├── /World/Table_1 (UsdGeom.Xform, center=[0.0, -1.05, 0.30])
├── /World/Table_2 (UsdGeom.Xform, center=[0.909, 0.525, 0.30])
├── /World/Table_3 (UsdGeom.Xform, center=[-0.909, 0.525, 0.30])
├── /World/FR3_1 (UsdGeom.Xform, base_xy=[0.0, -0.45])
│   └── /World/FR3_1/fr3_link0 (UsdPhysics.ArticulationRootAPI)
├── /World/FR3_2 (UsdGeom.Xform, base_xy=[0.3897, 0.225])
│   └── /World/FR3_2/fr3_link0 (UsdPhysics.ArticulationRootAPI)
├── /World/FR3_3 (UsdGeom.Xform, base_xy=[-0.3897, 0.225])
│   └── /World/FR3_3/fr3_link0 (UsdPhysics.ArticulationRootAPI)
├── /World/OverheadCamera (UsdGeom.Camera, top-down orthographic/perspective)
└── /World/Block{1..N} (UsdGeom.Cube / Mesh, RigidBodyAPI, CollisionAPI, mass=0.3kg)
```

### 3.2 Key PhysX & Fabric Properties
- Simulation Rate: 240 Hz Physics Substep, 50 Hz ROS 2 Controller loop.
- Broadphase: GPU SAP/MBP, Solver: TGS (Temporal Gauss-Seidel).
- Omniverse Fabric Scene Delegate enabled (`--/app/useFabricSceneDelegate=true`).

---

## 4. ROS 2 Interfaces & Message Specifications

### 4.1 Coordinate Frames (`/tf` and `/tf_static`)
- `world` (Global origin, aligned with center table center)
- `base_link_1`, `base_link_2`, `base_link_3` (Robot mounting bases)
- `fr3_1_link0` through `fr3_1_link8`, `fr3_1_hand`, `fr3_1_tcp`
- `fr3_2_link0` through `fr3_2_link8`, `fr3_2_hand`, `fr3_2_tcp`
- `fr3_3_link0` through `fr3_3_link8`, `fr3_3_hand`, `fr3_3_tcp`
- `overhead_camera_optical_frame`

### 4.2 Standard Sensor & Control Topics
| Topic Name | Type | Direction | Description |
| :--- | :--- | :--- | :--- |
| `/tf` | `tf2_msgs/msg/TFMessage` | Isaac Sim -> ROS | Dynamic transforms for all joints and prims |
| `/tf_static` | `tf2_msgs/msg/TFMessage` | Isaac Sim -> ROS | Static robot mounts & table frames |
| `/clock` | `rosgraph_msgs/msg/Clock` | Isaac Sim -> ROS | Simulation clock (GPU PhysX time) |
| `/fr3_1/joint_states` | `sensor_msgs/msg/JointState` | Isaac Sim -> ROS | 7 arm joints + 2 gripper finger positions |
| `/fr3_1/joint_commands` | `sensor_msgs/msg/JointState` | ROS -> Isaac Sim | Commanded joint position targets (50 Hz) |
| `/fr3_2/joint_states` | `sensor_msgs/msg/JointState` | Isaac Sim -> ROS | Arm 2 telemetry |
| `/fr3_2/joint_commands` | `sensor_msgs/msg/JointState` | ROS -> Isaac Sim | Arm 2 position commands |
| `/fr3_3/joint_states` | `sensor_msgs/msg/JointState` | Isaac Sim -> ROS | Arm 3 telemetry |
| `/fr3_3/joint_commands` | `sensor_msgs/msg/JointState` | ROS -> Isaac Sim | Arm 3 position commands |
| `/overhead_camera/rgb` | `sensor_msgs/msg/Image` | Isaac Sim -> VLA | RGB overhead synthetic frame (10 Hz) |
| `/overhead_camera/depth` | `sensor_msgs/msg/Image` | Isaac Sim -> VLA | Aligned 32FC1 depth map (10 Hz) |
| `/overhead_camera/camera_info` | `sensor_msgs/msg/CameraInfo` | Isaac Sim -> VLA | Intrinsic calibration parameters |

### 4.3 High-Level VLA Orchestration Topics
| Topic Name | Type | Description |
| :--- | :--- | :--- |
| `/gemini/custom_goal` | `std_msgs/msg/String` | Incoming human natural language command or test scenario |
| `/gemini/action` | `std_msgs/msg/String` | Serialized JSON action dispatched by Gemini function caller |
| `/gemini/feedback` | `std_msgs/msg/String` | Execution status (`SUCCESS`, `IN_PROGRESS`, `FAILED`, `ABORTED`) |

---

## 5. Gemini Robotics-ER Function Calling Schema (Tool Definitions)

When orchestrating multi-arm tasks, the reasoning loop employs structured function calling with the following static API schemas:

```json
[
  {
    "name": "detect_objects",
    "description": "Inspect overhead camera and return detected objects, colors, shapes, and 3D positions.",
    "parameters": { "type": "OBJECT", "properties": {} }
  },
  {
    "name": "pick",
    "description": "Pick up an object using the designated robot arm.",
    "parameters": {
      "type": "OBJECT",
      "properties": {
        "robot": { "type": "STRING", "enum": ["FR3_1", "FR3_2", "FR3_3"] },
        "object_label": { "type": "STRING", "description": "e.g. 'Red Cube', 'Blue Cylinder'" },
        "speed": { "type": "STRING", "enum": ["fast", "normal", "slow"], "default": "fast" },
        "approach_height": { "type": "NUMBER", "default": 0.1 }
      },
      "required": ["robot", "object_label"]
    }
  },
  {
    "name": "place",
    "description": "Place currently held object at absolute world (x, y) coordinates.",
    "parameters": {
      "type": "OBJECT",
      "properties": {
        "robot": { "type": "STRING", "enum": ["FR3_1", "FR3_2", "FR3_3"] },
        "x": { "type": "NUMBER" },
        "y": { "type": "NUMBER" },
        "speed": { "type": "STRING", "enum": ["fast", "normal", "slow"], "default": "fast" },
        "approach_height": { "type": "NUMBER", "default": 0.1 }
      },
      "required": ["robot", "x", "y"]
    }
  },
  {
    "name": "place_relative",
    "description": "Place held object relative to an existing anchor block on the target table.",
    "parameters": {
      "type": "OBJECT",
      "properties": {
        "robot": { "type": "STRING", "enum": ["FR3_1", "FR3_2", "FR3_3"] },
        "anchor_block": { "type": "STRING", "description": "Reference block label" },
        "relation": { "type": "STRING", "enum": ["on_top_of", "left_of", "right_of", "front_of", "back_of"] },
        "speed": { "type": "STRING", "enum": ["fast", "normal", "slow"], "default": "fast" },
        "approach_height": { "type": "NUMBER", "default": 0.1 }
      },
      "required": ["robot", "anchor_block", "relation"]
    }
  },
  {
    "name": "go_home",
    "description": "Return specified robot arm to safe home standby configuration.",
    "parameters": {
      "type": "OBJECT",
      "properties": {
        "robot": { "type": "STRING", "enum": ["FR3_1", "FR3_2", "FR3_3"] }
      },
      "required": ["robot"]
    }
  },
  {
    "name": "get_workspace_status",
    "description": "Query live robot status (idle/busy) and remaining blocks.",
    "parameters": { "type": "OBJECT", "properties": {} }
  },
  {
    "name": "verify_tower",
    "description": "Validate structural integrity and alignment of completed assembly.",
    "parameters": { "type": "OBJECT", "properties": {} }
  },
  {
    "name": "replan",
    "description": "Trigger multi-agent replanning if physical state deviates or slips occur.",
    "parameters": { "type": "OBJECT", "properties": {} }
  }
]
```

---

## 6. Context-Caching Optimization Rules for Gemini Sessions

1. **Static Invariant**: This document must remain byte-for-byte identical across runs. Dynamic runtime values (such as current block positions, joint angles, or execution counters) belong in runtime tool outputs or user turn prompts, NEVER in this file.
2. **Deterministic System Prefix**: Because this context is placed into `instructions` or agent prompt, Gemini servers automatically identify the identical prefix hash (>32k tokens) and cache the KV pairs, cutting token costs by 75–90% and accelerating inference.
3. **Cross-OS Command Invocation**: Commands interacting with the ROS 2 runtime from Windows must be wrapped in `wsl -d Ubuntu-24.04 bash -c "source /opt/ros/jazzy/setup.bash && ..."`.
