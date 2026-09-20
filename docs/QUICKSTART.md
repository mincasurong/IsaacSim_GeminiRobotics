# Quick Start Guide

Get the multi-robot tower stacking demo running from scratch.

---

## What You'll Need

| Requirement | Details |
|-------------|---------|
| **OS** | Windows 10 or 11 with WSL2 support |
| **GPU** | NVIDIA RTX 3060+ (8GB+ VRAM) |
| **RAM** | 16 GB minimum |
| **Disk** | 50 GB free (Isaac Sim + WSL2 + ROS 2) |
| **Isaac Sim** | Version 4.5+ or 6.0 ([NVIDIA Omniverse](https://www.nvidia.com/en-us/omniverse/)) |
| **Node.js** | 18+ (for the web dashboard) |
| **API Key** | Google Gemini API key ([free tier](https://aistudio.google.com/apikey)) |

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/mincasurong/IsaacSim_GeminiRobotics.git
cd IsaacSim_GeminiRobotics
```

---

## Step 2: Set Up WSL2 & ROS 2

Open PowerShell as Administrator:
```powershell
wsl --install -d Ubuntu-24.04
```

After Ubuntu is installed, open the WSL2 terminal and run:
```bash
cd /mnt/d/git/IsaacSim_GeminiRobotics/wsl_ws
chmod +x setup_all.sh
./setup_all.sh
```

> **Note**: This script installs ROS 2 Jazzy, Python packages, build tools, and configures FastDDS networking. It may take 15–30 minutes on the first run.

---

## Step 3: Configure Gemini API

```bash
# From the repository root
cp .env.example private/.env
```

Edit `private/.env` and add your API key:
```env
GEMINI_API_KEY=your_actual_api_key_here
ROBOTICS_MODEL=gemini-2.5-flash
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

## Step 5: Launch Everything

### Option A: Easy (Web Dashboard)

1. Double-click **`start_dashboard.bat`** in the project root
2. Your browser opens to `http://localhost:5173`
3. Click the **▶ Start** button in the top bar

### Option B: Manual (Terminals)

**Terminal 1** — Start the simulation from Isaac Sim:
```
Open Isaac Sim → File → Open Script → select isaacsim_scripts/three_robot_tower.py → Run
```

**Terminal 2** — Start ROS 2 controllers (WSL2):
```bash
cd /mnt/d/git/IsaacSim_GeminiRobotics/wsl_ws
./bringup.bash
# Select the desired launch option from the menu
```

---

## Step 6: Run the Simulation

In Isaac Sim, press the **▶ Play** button to start the physics simulation. You should see three Franka FR3 robots, colored blocks on three source tables, and an empty central target table.

---

## Step 7: Send a Goal

In the web dashboard (`http://localhost:5173`), you can:
- Click any of the **Quick Prompt Chips** above the input bar:
  - `⚡ Fast 9-Layer Tower`
  - `📐 3x3 Coplanar Grid`
  - `🔺 Triangle Pyramid`
  - `🔄 Table 1 to 3 Relay`
- Or type any custom spatial mission in natural language:
  > *"Arrange 6 blocks into a flat triangle formation on the central table"*

Switch to the **`[🔀 Workflow Graph]`** tab to watch the Gemini Multi-Agent team (Orchestrator 🦾, Spatial Architect 📐, Performance Optimizer ⚡) brainstorm the plan and dispatch parallel arm operations across FR3_1, FR3_2, and FR3_3 in real time!

---

## Step 8: Run Benchmark Experiments (Optional)

To run automated scientific evaluation trials:

```bash
# In WSL2 terminal
source /opt/ros/jazzy/setup.bash
source ~/catkin_ws/install/setup.bash

# Run 20 trials across scenarios S1, S2, and S3
ros2 run isaac_ros2_control experiment_runner --scenarios S1,S2,S3 --trials 20

# Compile publication-grade LaTeX tables & vector figures
ros2 run isaac_ros2_control analyze_experiments --log-dir /mnt/d/git/IsaacSim_GeminiRobotics/logs/experiments
```

---

## What's Next?

- 📖 **Deep Dive**: See [DEVELOPMENT.md](DEVELOPMENT.md) for full architecture and technical specifications
- 🎮 **Web GUI Guide**: See [gemini_web_gui/README.md](../gemini_web_gui/README.md) for React Flow dashboard details
- 📜 **Changelog**: Browse [CHANGELOG.md](CHANGELOG.md) for version release history
- 🔧 **Troubleshooting**: Check the [README troubleshooting section](../README.md#-troubleshooting)
