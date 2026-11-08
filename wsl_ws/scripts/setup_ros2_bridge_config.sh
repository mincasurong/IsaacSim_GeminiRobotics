#!/usr/bin/env bash
###############################################################################
# Phase 5b: ROS 2 DDS Bridge Configuration (WSL2 ↔ Windows)
#
# Generates FastDDS configuration files and sets environment variables
# for cross-boundary ROS 2 communication between:
#   - Isaac Sim (running on Windows)
#   - ROS 2 Jazzy (running in WSL2)
#
# Usage:  chmod +x scripts/setup_ros2_bridge_config.sh && ./scripts/setup_ros2_bridge_config.sh
###############################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
CONFIG_DIR="${PROJECT_ROOT}/config"
LOG_FILE="${PROJECT_ROOT}/logs/setup_ros2_bridge_config.log"
mkdir -p "$(dirname "$LOG_FILE")" "${CONFIG_DIR}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date '+%H:%M:%S')]${NC} $*" | tee -a "$LOG_FILE"; }
ok()   { echo -e "${GREEN}[✔]${NC} $*" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[!]${NC} $*" | tee -a "$LOG_FILE"; }

###############################################################################
# 1. Detect Network Configuration
###############################################################################
log "=== Detecting WSL2 Network Configuration ==="

# Get WSL2 IP address
WSL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "")
if [ -z "$WSL_IP" ]; then
    WSL_IP="127.0.0.1"
    warn "Could not detect WSL2 IP — using loopback"
fi

# Try to detect Windows host IP
WIN_IP=$(ip route show default 2>/dev/null | awk '{print $3}' || echo "")
if [ -z "$WIN_IP" ]; then
    # Fallback: try resolving hostname
    WIN_IP=$(cat /etc/resolv.conf 2>/dev/null | grep nameserver | awk '{print $2}' | head -1 || echo "")
fi

if [ -z "$WIN_IP" ]; then
    WIN_IP="<WINDOWS_HOST_IP>"
    warn "Could not auto-detect Windows host IP."
    warn "You'll need to manually set it in the config files."
fi

log "WSL2 IP:        ${WSL_IP}"
log "Windows Host IP: ${WIN_IP}"

###############################################################################
# 2. Generate FastDDS Profile XML
###############################################################################
log "=== Generating FastDDS Configuration ==="

FASTDDS_PROFILE="${CONFIG_DIR}/fastdds_profile.xml"

cat > "${FASTDDS_PROFILE}" << EOF
<?xml version="1.0" encoding="UTF-8" ?>
<!--
    FastDDS Configuration for WSL2 <-> Windows ROS 2 Bridge
    
    This profile configures DDS discovery so that ROS 2 nodes in WSL2
    can communicate with Isaac Sim's ROS 2 bridge on the Windows host.
    
    Usage:
      export FASTRTPS_DEFAULT_PROFILES_FILE=${FASTDDS_PROFILE}
    
    Auto-detected IPs:
      WSL2:    ${WSL_IP}
      Windows: ${WIN_IP}
    
    If IPs change (WSL2 restarts), re-run setup_ros2_bridge_config.sh
-->
<profiles xmlns="http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles">
    
    <!-- Default participant profile for all ROS 2 nodes -->
    <participant profile_name="default_participant" is_default_profile="true">
        <rtps>
            <builtin>
                <discovery_config>
                    <discoveryProtocol>SIMPLE</discoveryProtocol>
                    <leaseDuration>
                        <sec>10</sec>
                    </leaseDuration>
                </discovery_config>
                
                <metatrafficUnicastLocatorList>
                    <locator>
                        <udpv4>
                            <address>${WSL_IP}</address>
                        </udpv4>
                    </locator>
                </metatrafficUnicastLocatorList>
                
                <initialPeersList>
                    <!-- Windows host (where Isaac Sim runs) -->
                    <locator>
                        <udpv4>
                            <address>${WIN_IP}</address>
                        </udpv4>
                    </locator>
                    <!-- WSL2 (local) -->
                    <locator>
                        <udpv4>
                            <address>${WSL_IP}</address>
                        </udpv4>
                    </locator>
                </initialPeersList>
            </builtin>
            
            <defaultUnicastLocatorList>
                <locator>
                    <udpv4>
                        <address>${WSL_IP}</address>
                    </udpv4>
                </locator>
            </defaultUnicastLocatorList>
            
            <useBuiltinTransports>true</useBuiltinTransports>
        </rtps>
    </participant>
    
</profiles>
EOF

ok "FastDDS profile written to: ${FASTDDS_PROFILE}"

###############################################################################
# 3. Generate Windows-side FastDDS Profile
###############################################################################
WIN_FASTDDS_PROFILE="${CONFIG_DIR}/fastdds_profile_windows.xml"

cat > "${WIN_FASTDDS_PROFILE}" << EOF
<?xml version="1.0" encoding="UTF-8" ?>
<!--
    FastDDS Configuration for Windows (Isaac Sim side)
    
    Set this environment variable in PowerShell before launching Isaac Sim:
      \$env:FASTRTPS_DEFAULT_PROFILES_FILE = "<PATH_TO_PROJECT>\\config\\fastdds_profile_windows.xml"
    
    Auto-detected IPs:
      Windows: ${WIN_IP}
      WSL2:    ${WSL_IP}
-->
<profiles xmlns="http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles">
    
    <participant profile_name="default_participant" is_default_profile="true">
        <rtps>
            <builtin>
                <discovery_config>
                    <discoveryProtocol>SIMPLE</discoveryProtocol>
                    <leaseDuration>
                        <sec>10</sec>
                    </leaseDuration>
                </discovery_config>
                
                <initialPeersList>
                    <!-- WSL2 (where ROS 2 nodes run) -->
                    <locator>
                        <udpv4>
                            <address>${WSL_IP}</address>
                        </udpv4>
                    </locator>
                    <!-- Windows (local) -->
                    <locator>
                        <udpv4>
                            <address>${WIN_IP}</address>
                        </udpv4>
                    </locator>
                </initialPeersList>
            </builtin>
            
            <useBuiltinTransports>true</useBuiltinTransports>
        </rtps>
    </participant>
    
</profiles>
EOF

ok "Windows FastDDS profile written to: ${WIN_FASTDDS_PROFILE}"

###############################################################################
# 4. Update ~/.bashrc with Bridge Environment
###############################################################################
log "=== Updating Shell Environment ==="

BASHRC_MARKER="# >>> ROS2 DDS Bridge Config >>>"
if ! grep -qF "$BASHRC_MARKER" ~/.bashrc 2>/dev/null; then
    cat >> ~/.bashrc << BASHRC_BLOCK

${BASHRC_MARKER}
# FastDDS profile for WSL2 ↔ Windows Isaac Sim communication
export FASTRTPS_DEFAULT_PROFILES_FILE="${FASTDDS_PROFILE}"
# <<< ROS2 DDS Bridge Config <<<
BASHRC_BLOCK
    ok "FASTRTPS_DEFAULT_PROFILES_FILE added to ~/.bashrc"
else
    ok "DDS bridge config already in ~/.bashrc"
fi

###############################################################################
# 5. Connection Test Instructions
###############################################################################
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Phase 5b: DDS Bridge Configuration Complete${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Network Config:"
echo "    WSL2 IP:        ${WSL_IP}"
echo "    Windows Host:   ${WIN_IP}"
echo ""
echo "  Config Files:"
echo "    WSL2 side:    ${FASTDDS_PROFILE}"
echo "    Windows side: ${WIN_FASTDDS_PROFILE}"
echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Quick Test (after Isaac Sim is running with ROS2 bridge):"
echo ""
echo "  [WSL2 Terminal 1]"
echo "    source /opt/ros/jazzy/setup.bash"
echo "    ros2 topic list"
echo ""
echo "  Expected: Isaac Sim topics (/joint_states, /tf, /clock, etc.)"
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  ⚠  If WSL2 IP changes (after reboot), re-run this script."
echo ""
