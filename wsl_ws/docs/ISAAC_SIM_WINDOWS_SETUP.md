# Isaac Sim 4.5 — Windows Installation Guide

> **Isaac Sim runs natively on Windows.** It cannot run inside WSL2 due to
> Vulkan/RTX rendering requirements. Your WSL2 Ubuntu 24.04 runs the ROS 2
> side of the stack. They communicate via the ROS 2 DDS bridge.

## System Requirements Checklist

| Requirement | Your System | Status |
|---|---|---|
| OS | Windows 11 | ✅ Required (Win10 no longer supported) |
| GPU | RTX 2080 Ti (11GB) | ✅ Meets minimum (RTX 2070+) |
| VRAM | 11,264 MiB | ✅ 8GB min, 11GB good |
| RAM | Check: 32GB+ recommended | ❓ Verify |
| NVIDIA Driver | 566.36 | ✅ Min 537.xx for 4.5 |
| Python | 3.10 (required for 4.5) | ⚠️ Install below |
| Disk Space | ~30GB for Isaac Sim | ❓ Verify |

## Installation Options

### Option A: Pip Install (Recommended for Development / Isaac Lab)

This is the best approach for RL training with Isaac Lab and scripted workflows.

#### Step 1: Install Python 3.10

Isaac Sim 4.5 requires **exactly Python 3.10**.

1. Download from: https://www.python.org/downloads/release/python-31011/
2. During install, check **"Add Python to PATH"**
3. Verify in PowerShell:
   ```powershell
   python3.10 --version
   # Should output: Python 3.10.x
   ```

#### Step 2: Create Virtual Environment

```powershell
# Navigate to your preferred directory
cd D:\isaac_sim

# Create virtual environment with Python 3.10
python3.10 -m venv .venv

# Activate
.venv\Scripts\Activate.ps1
```

#### Step 3: Install Isaac Sim 4.5

```powershell
# Upgrade pip
pip install --upgrade pip

# Install Isaac Sim 4.5 with all extensions
pip install isaacsim[all]==4.5.0 --extra-index-url https://pypi.nvidia.com
```

> ⏱ This downloads ~10GB of packages. Be patient.

#### Step 4: Verify Installation

```powershell
# Run compatibility checker
isaacsim isaacsim.exp.compatibility_check

# Launch Isaac Sim GUI
isaacsim
```

### Option B: Standalone Binary (For GUI-heavy Workflows)

1. Visit the [Isaac Sim Downloads page](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_workstation.html)
2. Download the Windows standalone archive for version 4.5
3. Extract to `D:\isaac_sim\` (or your preferred location)
4. Run `isaac-sim.bat` or use `isaac-sim.selector.bat` to configure extensions

> ⚠️ **Do NOT use the Omniverse Launcher** — it was deprecated on Oct 1, 2025.

---

## Enabling the ROS 2 Bridge

The ROS 2 bridge allows Isaac Sim (Windows) to communicate with ROS 2 (WSL2).

### Using isaac-sim.selector.bat (Standalone Binary)

1. Run `isaac-sim.selector.bat` from your install directory
2. Enable: **ROS2 Bridge** (`omni.isaac.ros2_bridge`)
3. Disable: ROS1 Bridge (if listed)
4. Choose: **"Use Internal ROS2 Libraries"** (recommended for Windows)
5. Launch Isaac Sim

### Using Extension Manager (Any Install Method)

1. Launch Isaac Sim
2. Go to **Window → Extensions**
3. Search for `omni.isaac.ros2_bridge`
4. Enable it
5. Ensure `omni.isaac.ros_bridge` (ROS 1) is **disabled**

---

## Configuring the Windows ↔ WSL2 ROS 2 Bridge

### Environment Variables (Set in PowerShell before launching Isaac Sim)

```powershell
# Set ROS Domain ID (must match WSL2 side)
$env:ROS_DOMAIN_ID = "0"

# Use FastRTPS (must match WSL2 side)
$env:RMW_IMPLEMENTATION = "rmw_fastrtps_cpp"
```

Or add to your system environment variables permanently via:
- Settings → System → Advanced system settings → Environment Variables

### Networking (Critical for WSL2)

WSL2 has its own virtual network adapter. For DDS multicast discovery to work
between Windows and WSL2, you may need to:

#### Option 1: WSL2 Mirrored Networking (Simplest)

Edit `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
```

Then restart WSL: `wsl --shutdown` from PowerShell.

> ⚠️ Mirrored mode can be inconsistent with some DDS setups. Test first.

#### Option 2: FastDDS Discovery Server (Most Reliable)

Use the FastDDS Discovery Server configuration provided in
`config/fastdds_profile.xml` in this repository.

**On Windows (PowerShell):**
```powershell
$env:FASTRTPS_DEFAULT_PROFILES_FILE = "D:\git\isaacsim\config\fastdds_profile.xml"
```

**On WSL2 (bash):**
```bash
export FASTRTPS_DEFAULT_PROFILES_FILE="/mnt/d/git/isaacsim/config/fastdds_profile.xml"
```

### Firewall Configuration

Windows Defender Firewall may block DDS UDP traffic. Allow it:

1. Open **Windows Defender Firewall → Advanced settings**
2. **Inbound Rules → New Rule:**
   - Type: Port
   - Protocol: UDP
   - Ports: 7400-7500
   - Action: Allow
3. **Outbound Rules:** Create the same rule for outbound

Or via PowerShell (Administrator):
```powershell
New-NetFirewallRule -DisplayName "ROS2 DDS (Isaac Sim)" `
    -Direction Inbound -Protocol UDP -LocalPort 7400-7500 -Action Allow

New-NetFirewallRule -DisplayName "ROS2 DDS (Isaac Sim)" `
    -Direction Outbound -Protocol UDP -LocalPort 7400-7500 -Action Allow
```

---

## Testing the Bridge

### 1. Start Isaac Sim on Windows

```powershell
# With pip install:
$env:ROS_DOMAIN_ID = "0"
$env:RMW_IMPLEMENTATION = "rmw_fastrtps_cpp"
isaacsim
```

### 2. Load a Franka Panda Scene

In Isaac Sim:
1. Go to **Isaac Examples → Manipulation → Franka**
2. Or create a new scene:
   - **Create → Isaac → Robots → Franka**
3. Press **Play** (▶) to start simulation

### 3. Verify Topics from WSL2

```bash
# In WSL2 terminal
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# List topics — should see Isaac Sim topics
ros2 topic list

# Expected topics from Franka scene:
#   /joint_states
#   /tf
#   /tf_static
#   /clock
```

### 4. Echo Joint States

```bash
ros2 topic echo /joint_states
```

You should see real-time joint position data from the simulated Franka Panda.

---

## Isaac Lab Setup (For RL Training)

Isaac Lab provides a reinforcement learning framework on top of Isaac Sim.

### Install Isaac Lab (compatible with Isaac Sim 4.5)

```powershell
# Inside your Isaac Sim Python 3.10 venv on Windows
cd D:\

# Clone Isaac Lab
git clone https://github.com/isaac-sim/IsaacLab.git
cd IsaacLab

# Install (this detects your Isaac Sim installation)
pip install -e .

# Verify
python -c "import isaaclab; print('Isaac Lab ready')"
```

### First RL Training Run

```powershell
# Train a Franka reach task
python scripts/rsl_rl/train.py --task Isaac-Reach-Franka-v0 --headless
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `isaacsim` command not found | Activate venv: `.venv\Scripts\Activate.ps1` |
| GLFW initialization failed | Update NVIDIA driver to latest |
| No topics visible from WSL2 | Check `ROS_DOMAIN_ID` matches, check firewall |
| Extension errors | Run: `isaacsim isaacsim.exp.compatibility_check` |
| CUDA out of memory | Close other GPU apps, reduce scene complexity |
| Omniverse Launcher? | **Deprecated** — use pip or standalone binary |
