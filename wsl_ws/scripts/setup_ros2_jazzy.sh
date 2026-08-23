#!/usr/bin/env bash
###############################################################################
# Phase 3: ROS 2 Jazzy Jalisco — Native Installation
#
# Installs ROS 2 Jazzy on Ubuntu 24.04 with the full desktop stack,
# plus MoveIt2, Nav2, ros2_control, and Franka-specific packages.
#
# Usage:  chmod +x scripts/setup_ros2_jazzy.sh && ./scripts/setup_ros2_jazzy.sh
###############################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/../logs/setup_ros2_jazzy.log"
mkdir -p "$(dirname "$LOG_FILE")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date '+%H:%M:%S')]${NC} $*" | tee -a "$LOG_FILE"; }
ok()   { echo -e "${GREEN}[✔]${NC} $*" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[!]${NC} $*" | tee -a "$LOG_FILE"; }
fail() { echo -e "${RED}[✘]${NC} $*" | tee -a "$LOG_FILE"; exit 1; }

###############################################################################
# 0. Pre-check: Verify Ubuntu 24.04
###############################################################################
UBUNTU_CODENAME=$(. /etc/os-release && echo "$UBUNTU_CODENAME")
if [ "$UBUNTU_CODENAME" != "noble" ]; then
    warn "Expected Ubuntu 24.04 (noble), found: $UBUNTU_CODENAME"
    warn "ROS 2 Jazzy is designed for Ubuntu 24.04. Proceeding anyway..."
fi

###############################################################################
# 1. Locale Setup
###############################################################################
log "=== Phase 3.1: Ensuring UTF-8 Locale ==="

sudo apt-get update -qq && sudo apt-get install -y -qq locales > /dev/null 2>&1
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

ok "Locale configured"

###############################################################################
# 2. Enable Required Repositories
###############################################################################
log "=== Phase 3.2: Configuring APT Repositories ==="

sudo apt-get install -y -qq software-properties-common > /dev/null 2>&1
sudo add-apt-repository -y universe 2>/dev/null || true

# Ensure ubuntu sources include updates and backports
if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then
    if ! grep -q "noble-updates" /etc/apt/sources.list.d/ubuntu.sources 2>/dev/null; then
        warn "Adding noble-updates and noble-backports to sources..."
        sudo sed -i 's/Suites: noble/Suites: noble noble-updates noble-backports/' \
            /etc/apt/sources.list.d/ubuntu.sources 2>/dev/null || true
    fi
fi

sudo apt-get update -qq
sudo apt-get full-upgrade -y -qq 2>&1 | tail -3 | tee -a "$LOG_FILE"

ok "Repositories configured"

###############################################################################
# 3. Add ROS 2 APT Repository
###############################################################################
log "=== Phase 3.3: Adding ROS 2 Repository ==="

sudo apt-get install -y -qq curl > /dev/null 2>&1

# Add ROS 2 GPG key
if [ ! -f /usr/share/keyrings/ros-archive-keyring.gpg ]; then
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg
fi

# Add ROS 2 repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | \
    sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt-get update -qq

ok "ROS 2 APT repository added"

###############################################################################
# 4. Install ROS 2 Jazzy Desktop
###############################################################################
log "=== Phase 3.4: Installing ROS 2 Jazzy Desktop ==="
log "This may take several minutes..."

sudo apt-get install -y ros-jazzy-desktop 2>&1 | tail -10 | tee -a "$LOG_FILE"

ok "ROS 2 Jazzy Desktop installed"

###############################################################################
# 5. Install Development Tools
###############################################################################
log "=== Phase 3.5: Installing ROS 2 Development Tools ==="

sudo apt-get install -y -qq ros-dev-tools 2>&1 | tail -3 | tee -a "$LOG_FILE"

ok "Development tools installed (colcon, rosdep, vcstool, etc.)"

###############################################################################
# 6. Initialize rosdep
###############################################################################
log "=== Phase 3.6: Initializing rosdep ==="

if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
    sudo rosdep init 2>&1 | tee -a "$LOG_FILE" || true
fi
rosdep update 2>&1 | tail -5 | tee -a "$LOG_FILE"

ok "rosdep initialized"

###############################################################################
# 7. Install Robotics Packages
###############################################################################
log "=== Phase 3.7: Installing Robotics Packages ==="

# Source ROS 2 for any post-install checks
source /opt/ros/jazzy/setup.bash

# --- Manipulation ---
log "Installing MoveIt 2 (motion planning framework)..."
sudo apt-get install -y -qq \
    ros-jazzy-moveit \
    ros-jazzy-moveit-planners \
    ros-jazzy-moveit-ros-visualization \
    ros-jazzy-moveit-servo \
    2>&1 | tail -3 | tee -a "$LOG_FILE"
ok "MoveIt 2 installed"

# --- Navigation ---
log "Installing Nav2 (navigation stack)..."
sudo apt-get install -y -qq \
    ros-jazzy-navigation2 \
    ros-jazzy-nav2-bringup \
    2>&1 | tail -3 | tee -a "$LOG_FILE"
ok "Nav2 installed"

# --- Control ---
log "Installing ros2_control..."
sudo apt-get install -y -qq \
    ros-jazzy-ros2-control \
    ros-jazzy-ros2-controllers \
    ros-jazzy-controller-manager \
    2>&1 | tail -3 | tee -a "$LOG_FILE"
ok "ros2_control installed"

# --- Robot Description Utilities ---
log "Installing robot description utilities..."
sudo apt-get install -y -qq \
    ros-jazzy-xacro \
    ros-jazzy-joint-state-publisher \
    ros-jazzy-joint-state-publisher-gui \
    ros-jazzy-robot-state-publisher \
    ros-jazzy-urdf \
    ros-jazzy-rviz2 \
    2>&1 | tail -3 | tee -a "$LOG_FILE"
ok "Robot description utilities installed"

# --- Franka Panda (if available in apt) ---
log "Checking for Franka ROS 2 packages..."
if apt-cache search ros-jazzy-franka 2>/dev/null | grep -q "franka"; then
    sudo apt-get install -y -qq ros-jazzy-franka-description 2>&1 | tail -3 | tee -a "$LOG_FILE" || true
    ok "Franka description package installed"
else
    warn "Franka packages not in apt — will need to build from source (see Isaac Sim assets)"
fi

# --- DDS middleware (FastRTPS for Isaac Sim bridge) ---
log "Installing FastDDS RMW implementation..."
sudo apt-get install -y -qq \
    ros-jazzy-rmw-fastrtps-cpp \
    ros-jazzy-rmw-fastrtps-shared-cpp \
    2>&1 | tail -3 | tee -a "$LOG_FILE"
ok "FastDDS RMW installed"

# --- Additional useful packages ---
log "Installing additional tools..."
sudo apt-get install -y -qq \
    ros-jazzy-rqt \
    ros-jazzy-rqt-common-plugins \
    ros-jazzy-rqt-tf-tree \
    ros-jazzy-rqt-graph \
    ros-jazzy-rqt-robot-steering \
    ros-jazzy-tf2-tools \
    ros-jazzy-tf-transformations \
    2>&1 | tail -3 | tee -a "$LOG_FILE"
ok "Additional tools installed"

###############################################################################
# 8. Configure ~/.bashrc
###############################################################################
log "=== Phase 3.8: Configuring Shell Environment ==="

BASHRC_MARKER="# >>> ROS 2 Jazzy (Isaac Sim Robotics Setup) >>>"
if ! grep -qF "$BASHRC_MARKER" ~/.bashrc 2>/dev/null; then
    cat >> ~/.bashrc << 'BASHRC_BLOCK'

# >>> ROS 2 Jazzy (Isaac Sim Robotics Setup) >>>
source /opt/ros/jazzy/setup.bash

# ROS 2 DDS configuration for Isaac Sim bridge
export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# Colcon defaults
export COLCON_LOG_LEVEL=30

# Useful aliases
alias cb='colcon build --symlink-install'
alias cs='source install/setup.bash'
alias cbt='colcon build --symlink-install && source install/setup.bash'
alias rtl='ros2 topic list'
alias rnl='ros2 node list'

# Source workspace overlay if exists
if [ -f ~/ros2_ws/install/setup.bash ]; then
    source ~/ros2_ws/install/setup.bash
fi
# <<< ROS 2 Jazzy (Isaac Sim Robotics Setup) <<<
BASHRC_BLOCK
    ok "~/.bashrc updated with ROS 2 environment"
else
    ok "~/.bashrc already configured for ROS 2"
fi

###############################################################################
# 9. Create default ROS 2 workspace
###############################################################################
log "=== Phase 3.9: Creating Default Workspace ==="

mkdir -p ~/ros2_ws/src
ok "Default workspace created at ~/ros2_ws/"

###############################################################################
# 10. Verification
###############################################################################
log "=== Phase 3.10: Verifying ROS 2 Installation ==="

source /opt/ros/jazzy/setup.bash

ROS_DISTRO_CHECK=$(printenv ROS_DISTRO 2>/dev/null || echo "not set")
if [ "$ROS_DISTRO_CHECK" = "jazzy" ]; then
    ok "ROS_DISTRO = jazzy ✓"
else
    fail "ROS_DISTRO = $ROS_DISTRO_CHECK (expected jazzy)"
fi

# Quick test
if ros2 pkg list 2>/dev/null | grep -q "moveit"; then
    ok "MoveIt 2 packages available"
fi
if ros2 pkg list 2>/dev/null | grep -q "nav2"; then
    ok "Nav2 packages available"
fi

###############################################################################
# Summary
###############################################################################
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Phase 3 Complete: ROS 2 Jazzy Installed${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  ROS 2 Distro:   Jazzy Jalisco"
echo "  Desktop:        ros-jazzy-desktop"
echo "  MoveIt 2:       ✓ (motion planning)"
echo "  Nav2:           ✓ (navigation)"
echo "  ros2_control:   ✓ (hardware abstraction)"
echo "  DDS:            FastRTPS (for Isaac Sim bridge)"
echo "  Workspace:      ~/ros2_ws/"
echo ""
echo "  Test: source /opt/ros/jazzy/setup.bash && ros2 run demo_nodes_cpp talker"
echo ""
echo "  Next step: Run ./scripts/setup_isaac_ros_workspace.sh (Phase 4)"
echo ""
