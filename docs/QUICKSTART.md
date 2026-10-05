# Quick Start Guide

Get the multi-robot manipulation and Physical AI demo running from scratch.

---

## What You'll Need

| Requirement | Details |
|---|---|
| **OS** | Windows 10 or 11 with WSL2 support |
| **GPU** | NVIDIA RTX 3060+ (8 GB+ VRAM) |
| **RAM** | 16 GB minimum (32 GB recommended) |
| **Disk** | 50 GB free space (Isaac Sim + WSL2 + ROS 2) |
| **Isaac Sim** | Version 4.5+ or 6.0 ([NVIDIA Omniverse](https://developer.nvidia.com/isaac-sim)) |
| **Node.js** | 18+ (for the web dashboard) |
| **API Key** | Google Gemini API key ([free tier from AI Studio](https://aistudio.google.com/apikey)) |

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/mincasurong/IsaacSim_Gemini.git
cd IsaacSim_Gemini
```

---

## Step 2: Set Up WSL2 & ROS 2 Jazzy

Open PowerShell as Administrator:
```powershell
wsl --install -d Ubuntu-24.04
```

After Ubuntu is installed, open the WSL2 terminal and run:
```bash
cd /mnt/d/git/IsaacSim_Gemini/wsl_ws
chmod +x setup_all.sh
./setup_all.sh
```

> **Note**: This script installs ROS 2 Jazzy Jalisco, build tools (`colcon`), Python dependencies (`google-genai`, `cv_bridge`), and generates FastDDS unicast network profiles.

---

## Step 3: Configure Gemini API Key & Models

Copy the environment template:
```bash
# In the repository root on Windows
cp .env.example private/.env
```

Edit `private/.env` and configure your API key and model tiers:
```env
GEMINI_API_KEY=your_actual_api_key_here

# Tier 1: Spatial Architect & DAG Generator (4M TPM Quota, No Coding Agent Contention)
PLANNER_MODEL=gemini-3.5-flash-lite

# Tier 2: Physical VLA Orchestrator (Visual Action Tool Calling)
ROBOTICS_MODEL=gemini-robotics-er-2-preview

# Tier 3: Real-Time Diagnostic Auditor (Background Log Analysis)
MONITORING_MODEL=gemini-3.5-flash-lite

# Execution Mode: 'visual_flow' (deterministic zero-token node workflow) or 'vla' (Gemini autonomous)
EXECUTION_MODE=visual_flow
```

Get a free key from [Google AI Studio](https://aistudio.google.com/apikey).

---

## Step 4: Set Up the Web Dashboard

```bash
cd gemini_web_gui
npm install
npm run build
```

---

## Step 5: Clean Zombie Processes & Launch

### Recommended: Clean Zombie Simulator Processes First
If you previously ran Isaac Sim, ensure no orphaned processes linger in the background:
```powershell
Stop-Process -Name "kit" -Force -ErrorAction SilentlyContinue
```

### Option A: Unified Windows Launcher (Recommended)
Run `scripts/launcher.bat` on Windows. You can choose any of the available scenarios:
* `[1]` **3x FR3 + Gemini VLM (9-Layer Tower Stacking)**
* `[2]` **Standalone 3x FR3 Rule-Based Stacking (No API key needed)**
* `[3]` **Nova Carter Mobile Manipulator**
* `[4]` **MoveIt 2 Motion Planning (MoveItPy + Trajectory Adapter)**
* `[5]` **Dual-Arm Conveyor Interception & Circular Wave Motion**
* `[6]` **Dual-Arm Collaborative Assembly**
* `[0]` **Launch Web GUI + Digital Twin Dashboard**

### Option B: Web Dashboard + Isaac Sim
1. Run `scripts/start_dashboard.bat` (browser opens to `http://localhost:5173`).
2. Open Isaac Sim on Windows, load `isaacsim_scripts/three_robot_tower.py` (or `conveyor_dual_robot.py`), and press **▶ Play**.
3. In WSL2, start the controller:
   ```bash
   cd /mnt/d/git/IsaacSim_Gemini/wsl_ws
   ./bringup.bash
   ```

---

## Step 6: Send a Goal

In the web dashboard (`http://localhost:5173`), you can:
- Click any **Quick Prompt Chip**:
  - `⚡ Fast 9-Layer Tower`
  - `📐 3x3 Coplanar Grid`
  - `🔺 Triangle Pyramid`
  - `🔄 Table 1 to 3 Relay`
- Or enter a natural language directive:
  > *"Arrange 6 blocks into a flat triangle formation on the central table"*

Switch to the **`[🔀 Workflow Graph]`** tab to view the live multi-agent reasoning:
1. **Spatial Architect 📐 (Gemini 3.8 Flash)** outputs the 2D ASCII plan.
2. **Agility Optimizer ⚡** evaluates parallel arm speeds.
3. **Orchestrator 🦾 (Gemini Robotics-ER 2)** dispatches synchronized `pick`, `place`, and `place_relative` actions.
4. **Health Auditor 🛡️ (Gemini 3.5 Flash-Lite)** monitors `/rosout` telemetry and verifies physical execution.

---

## Step 7: Antigravity 2.0 & OpenCode Integration

### Using Antigravity 2.0 (Autonomous Ralph Loop)
The project includes pre-configured autonomous permissions in `.antigravity/permissions.json`. Launch autonomous goals using:
```bash
/goal Run 10 benchmark trials for scenario S2 and compile the LaTeX results table
```

### Using OpenCode
The repository defines an OpenCode agent (`opencode.json`):
* Agent Persona: `.opencode/agent/physical-ai-orchestrator.md` using `google/gemini-3.8-flash`.
* Built-in ROS 2 MCP Server (`wsl_ws/scripts/ros2_mcp.py`) allowing coding agents to query topics and run services directly.

---

## Step 8: Run Benchmark Experiments (Optional)

To execute scientific evaluation trials:

```bash
# In WSL2 terminal with ROS 2 environment sourced:
source /opt/ros/jazzy/setup.bash
source ~/catkin_ws/install/setup.bash

# Run 20 trials across scenarios S1, S2, and S3
ros2 run isaac_ros2_control experiment_runner --scenarios S1,S2,S3 --trials 20

# Compile publication-grade LaTeX tables & vector figures
ros2 run isaac_ros2_control analyze_experiments --log-dir /mnt/d/git/IsaacSim_Gemini/logs/experiments
```

---

## What's Next?

- 📖 **Deep Dive**: See [DEVELOPMENT.md](DEVELOPMENT.md) for full architecture and technical specifications.
- 🎮 **Web GUI Guide**: See [gemini_web_gui/README.md](../gemini_web_gui/README.md) for React Flow dashboard details.
- 📜 **Changelog**: Browse [CHANGELOG.md](CHANGELOG.md) for version release history.
- 🔧 **Troubleshooting**: Check the [README troubleshooting section](../README.md#-troubleshooting).
