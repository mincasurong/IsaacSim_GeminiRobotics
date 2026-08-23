#!/usr/bin/env bash
###############################################################################
# ROS 2 WSL2 Bringup Script
#
# Automatically syncs workspace source files from the Windows mount,
# configures the FastDDS environment, and launches selected ROS 2 targets.
###############################################################################

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
BOLD='\033[1m'

echo -e "${BOLD}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   🤖  WSL2 ROS 2 Bringup & Environment Configurator           ║${NC}"
echo -e "${BOLD}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 0. Sync workspace packages from Windows mount to WSL2 workspace
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$SCRIPT_DIR" == /mnt/* ]] && [ -d "$SCRIPT_DIR/src" ]; then
    WINDOWS_WS_DIR="$SCRIPT_DIR"
else
    # Fallback paths
    if [ -d "/mnt/d/git/IsaacSim_Gemini/wsl_ws" ]; then
        WINDOWS_WS_DIR="/mnt/d/git/IsaacSim_Gemini/wsl_ws"
    else
        WINDOWS_WS_DIR="/mnt/d/git/isaacsim/src/isaacsim/wsl_ws"
    fi
fi

if [ -d "$WINDOWS_WS_DIR" ]; then
    echo -e "${GREEN}[INFO] Windows mount detected. Synchronizing workspace source files...${NC}"
    mkdir -p "${HOME}/catkin_ws/src"
    
    # Sync package source files (using rsync if available, fallback to cp)
    if command -v rsync >/dev/null 2>&1; then
        rsync -ru --delete "$WINDOWS_WS_DIR/src/" "${HOME}/catkin_ws/src/"
    else
        cp -ru "$WINDOWS_WS_DIR/src"/* "${HOME}/catkin_ws/src/"
    fi
    
    # Normalize line endings on synced Python/CMake files to prevent script errors
    find "${HOME}/catkin_ws/src/" -type f \( -name "*.py" -name "*.xml" -name "*.cfg" -name "*.txt" \) -exec sed -i 's/\r$//' {} + 2>/dev/null
    
    # Process extensionless direct scripts (remove \r and make executable)
    SCRIPT_DIR="${HOME}/catkin_ws/src/isaac_ros2_control/scripts"
    if [ -d "$SCRIPT_DIR" ]; then
        find "$SCRIPT_DIR" -type f -exec sed -i 's/\r$//' {} + 2>/dev/null
        find "$SCRIPT_DIR" -type f -exec chmod +x {} + 2>/dev/null
    fi
    
    # Sync this bringup script itself to ~/catkin_ws/ for future runs
    if [ -f "$WINDOWS_WS_DIR/bringup.bash" ]; then
        cp "$WINDOWS_WS_DIR/bringup.bash" "${HOME}/catkin_ws/bringup.bash"
        chmod +x "${HOME}/catkin_ws/bringup.bash"
        sed -i 's/\r$//' "${HOME}/catkin_ws/bringup.bash"
    fi
    echo -e "${GREEN}[INFO] Synchronization complete!${NC}"
else
    echo -e "${YELLOW}[WARNING] Windows mount not found at: ${WINDOWS_WS_DIR}${NC}"
    echo -e "          Running with local WSL2 workspace files only.${NC}"
fi

# 1. Use the FastDDS profile already written by the Windows launcher
LOCAL_PROFILE_PATH="${HOME}/fastdds_profile.xml"

# Fallback: copy from Windows mount if direct write didn't happen
if [ ! -f "$LOCAL_PROFILE_PATH" ]; then
    WINDOWS_PROFILE_PATH="/mnt/d/git/isaacsim/src/isaacsim/fastdds_profile.xml"
    if [ -f "$WINDOWS_PROFILE_PATH" ]; then
        echo -e "${GREEN}[INFO] Copying FastDDS profile from Windows mount...${NC}"
        cp "$WINDOWS_PROFILE_PATH" "$LOCAL_PROFILE_PATH"
        sed -i 's/\r$//' "$LOCAL_PROFILE_PATH"
    else
        echo -e "${RED}[ERROR] No FastDDS profile found! Please run run_fr3_wsl.bat on Windows first.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}[INFO] Using FastDDS profile at: ${LOCAL_PROFILE_PATH}${NC}"
    sed -i 's/\r$//' "$LOCAL_PROFILE_PATH"
fi

# Show the IPs being used
echo -e "${CYAN}[INFO] FastDDS peer addresses:${NC}"
grep -oP '(?<=<address>)[^<]+' "$LOCAL_PROFILE_PATH" | while read ip; do
    echo -e "       → $ip"
done

# 2. Export environment variables
echo -e "${GREEN}[INFO] Exporting environment variables...${NC}"
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTDDS_DEFAULT_PROFILES_FILE="${LOCAL_PROFILE_PATH}"
echo -e "       RMW_IMPLEMENTATION = ${RMW_IMPLEMENTATION}"
echo -e "       FASTDDS_DEFAULT_PROFILES_FILE = ${FASTDDS_DEFAULT_PROFILES_FILE}"

# 3. Source ROS 2 environment
if [ -f "/opt/ros/jazzy/setup.bash" ]; then
    echo -e "${GREEN}[INFO] Sourcing ROS 2 Jazzy...${NC}"
    source /opt/ros/jazzy/setup.bash
else
    echo -e "${RED}[ERROR] ROS 2 Jazzy not found in /opt/ros/jazzy/setup.bash!${NC}"
    exit 1
fi

# 4. Source workspace overlay
WORKSPACE_SETUP="${HOME}/catkin_ws/install/setup.bash"
if [ -f "$WORKSPACE_SETUP" ]; then
    echo -e "${GREEN}[INFO] Sourcing workspace overlay...${NC}"
    source "$WORKSPACE_SETUP"
else
    echo -e "${YELLOW}[WARNING] Workspace overlay not found at: ${WORKSPACE_SETUP}${NC}"
    echo -e "          Please build the workspace using 'colcon build' if needed.${NC}"
fi

# 5. Stop the ROS 2 daemon so it picks up the new FastDDS profile
echo -e "${GREEN}[INFO] Stopping stale ROS 2 daemon...${NC}"
ros2 daemon stop 2>/dev/null || true

# 6. Quick connectivity test (non-blocking)
WINDOWS_IP=$(grep -oP '(?<=<address>)[^<]+' "$LOCAL_PROFILE_PATH" | head -1)
echo -e "${CYAN}[INFO] Pinging Windows host ($WINDOWS_IP)...${NC}"
if ping -c 1 -W 2 "$WINDOWS_IP" > /dev/null 2>&1; then
    echo -e "${GREEN}[OK] Windows host is reachable!${NC}"
else
    echo -e "${RED}[WARNING] Cannot ping Windows host ($WINDOWS_IP).${NC}"
    echo -e "${RED}         Firewall may be blocking WSL2 traffic.${NC}"
    echo -e "${RED}         Run this in an Admin PowerShell on Windows:${NC}"
    echo -e "${YELLOW}         New-NetFirewallRule -DisplayName 'WSL2 ROS2 DDS' -Direction Inbound -InterfaceAlias 'vEthernet (WSL)' -Action Allow${NC}"
fi

echo ""
echo -e "${CYAN}=================================================================${NC}"
echo -e "${CYAN}                 WSL2 ROS 2 Orchestrator Menu                    ${NC}"
echo -e "${CYAN}=================================================================${NC}"
echo -e "  ${BOLD}1)${NC} [Gemini]  Start VLM Orchestrator ${GREEN}(Autonomous, Recommended)${NC}"
echo -e "  ${BOLD}2)${NC} [Manual]  Start Rule-Based Stacker (Fixed Sequence)"
echo -e "  ${BOLD}3)${NC} [Debug]   Start Controller Node Only"
echo -e "  ${BOLD}4)${NC} [Shell]   Enter ROS 2 Interactive Shell ${YELLOW}(Default)${NC}"
echo -e "  ${BOLD}5)${NC} [Topic]   Echo a ROS 2 Topic"
echo -e "  ${BOLD}6)${NC} [Service] Trigger /gemini/plan_task"
echo -e "${CYAN}=================================================================${NC}"
echo ""
echo -en "${GREEN}Enter your choice [1-6, default: 4] > ${NC}"
read OPTION

case "$OPTION" in
    1)
        echo -e "\n${GREEN}[LAUNCH] Starting 3x FR3 Gemini Robotics controller...${NC}"
        ros2 launch rosbridge_server rosbridge_websocket_launch.xml &
        ros2 launch isaac_ros2_control gemini_controller.launch.py
        ;;
    2)
        echo -e "\n${GREEN}[LAUNCH] Starting 3x FR3 rule-based stacking controller...${NC}"
        ros2 launch isaac_ros2_control multi_robot_rule_based.launch.py
        ;;
    3)
        echo -e "\n${GREEN}[LAUNCH] Starting multi-robot controller node...${NC}"
        ros2 launch isaac_ros2_control multi_robot_controller.launch.py
        ;;
    5)
        read -p "Enter topic name to echo [/clock]: " TOPIC
        TOPIC=${TOPIC:-/clock}
        echo -e "\n${GREEN}[LAUNCH] Echoing topic $TOPIC...${NC}"
        ros2 topic echo "$TOPIC"
        ;;
    6)
        echo -e "\n${GREEN}[TRIGGER] Calling /gemini/plan_task service...${NC}"
        ros2 service call /gemini/plan_task std_srvs/srv/Trigger
        ;;
    *)
        echo -e "\n${GREEN}[SHELL] Environment loaded. You can now run any ROS 2 commands.${NC}"
        bash
        ;;
esac
