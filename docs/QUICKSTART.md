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

In the web dashboard chat, type:

> *"Build a 9-layer tower using all three robots"*

Watch the Gemini VLA agent decompose the task, assign blocks to robots, and execute coordinated pick-and-place operations in real time!

---

## What's Next?

- 📖 **Deep Dive**: See [DEVELOPMENT.md](DEVELOPMENT.md) for architecture and contributor setup
- 🔧 **Troubleshooting**: Check the [README troubleshooting section](../README.md#-troubleshooting)
- 📝 **History**: Browse [DEV_LOG.md](DEV_LOG.md) for engineering notes and decisions
