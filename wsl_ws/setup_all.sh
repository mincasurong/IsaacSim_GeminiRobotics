#!/usr/bin/env bash
###############################################################################
# Master Setup Script — Isaac Sim + Isaac ROS Robotics Environment
#
# Runs all setup phases in sequence for the WSL2 Ubuntu 24.04 side.
# Isaac Sim installation on Windows must be done separately.
#
# Usage:
#   chmod +x setup_all.sh && ./setup_all.sh          # Run all phases
#   ./setup_all.sh --phase 3                          # Run specific phase
#   ./setup_all.sh --from 2                           # Resume from phase 2
###############################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
BOLD='\033[1m'

###############################################################################
# Parse arguments
###############################################################################
RUN_PHASE=""
FROM_PHASE=1

while [[ $# -gt 0 ]]; do
    case $1 in
        --phase) RUN_PHASE="$2"; shift 2 ;;
        --from)  FROM_PHASE="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--phase N] [--from N]"
            echo "  --phase N   Run only phase N (1-5)"
            echo "  --from N    Run from phase N onwards"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

###############################################################################
# Header
###############################################################################
echo ""
echo -e "${BOLD}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║                                                               ║${NC}"
echo -e "${BOLD}║   🤖  Isaac Sim + Isaac ROS — Robotics Environment Setup      ║${NC}"
echo -e "${BOLD}║                                                               ║${NC}"
echo -e "${BOLD}║   Target: Franka Panda Manipulator + Mobile Robots            ║${NC}"
echo -e "${BOLD}║   GPU:    NVIDIA RTX 2080 Ti (11GB)                           ║${NC}"
echo -e "${BOLD}║   Stack:  Isaac Sim 4.5 (Win) + ROS 2 Jazzy (WSL2)           ║${NC}"
echo -e "${BOLD}║                                                               ║${NC}"
echo -e "${BOLD}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

###############################################################################
# Run a phase
###############################################################################
run_phase() {
    local phase_num=$1
    local phase_name=$2
    local script=$3

    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  Phase ${phase_num}: ${phase_name}${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    if [ ! -f "${SCRIPT_DIR}/${script}" ]; then
        echo -e "${RED}Script not found: ${script}${NC}"
        return 1
    fi

    chmod +x "${SCRIPT_DIR}/${script}"
    bash "${SCRIPT_DIR}/${script}"

    echo -e "${GREEN}  ✔ Phase ${phase_num} complete${NC}"
}

should_run() {
    local phase=$1
    if [ -n "$RUN_PHASE" ]; then
        [ "$phase" -eq "$RUN_PHASE" ]
    else
        [ "$phase" -ge "$FROM_PHASE" ]
    fi
}

###############################################################################
# Execute Phases
###############################################################################

# Create logs directory
mkdir -p "${SCRIPT_DIR}/logs"

if should_run 1; then
    run_phase 1 "WSL2 System Preparation" "scripts/setup_wsl2_base.sh"
fi

if should_run 2; then
    run_phase 2 "Docker + NVIDIA Container Toolkit" "scripts/setup_docker_nvidia.sh"
fi

if should_run 3; then
    run_phase 3 "ROS 2 Jazzy Installation" "scripts/setup_ros2_jazzy.sh"
fi

if should_run 4; then
    run_phase 4 "Isaac ROS Workspace Setup" "scripts/setup_isaac_ros_workspace.sh"
fi

if should_run 5; then
    run_phase 5 "DDS Bridge Configuration" "scripts/setup_ros2_bridge_config.sh"
fi

###############################################################################
# Final Summary
###############################################################################
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                               ║${NC}"
echo -e "${GREEN}║   ✔  WSL2 Setup Complete!                                     ║${NC}"
echo -e "${GREEN}║                                                               ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  ┌─────────────────────────────────────────────────────────────┐"
echo "  │  What's installed (WSL2 side):                              │"
echo "  │    ✔ Build tools, Python, Git LFS                          │"
echo "  │    ✔ Docker + NVIDIA Container Toolkit                     │"
echo "  │    ✔ ROS 2 Jazzy (MoveIt2, Nav2, ros2_control)            │"
echo "  │    ✔ Isaac ROS workspace (~8 packages)                     │"
echo "  │    ✔ DDS bridge config (FastRTPS)                          │"
echo "  │                                                             │"
echo "  │  ⚠  REMAINING (Windows side — do manually):                │"
echo "  │    → Install Isaac Sim 4.5 on Windows                      │"
echo "  │    → Install Isaac Lab (for RL training)                   │"
echo "  │    → See: docs/ISAAC_SIM_WINDOWS_SETUP.md                 │"
echo "  └─────────────────────────────────────────────────────────────┘"
echo ""
echo "  Run the health check:"
echo "    ./scripts/verify_setup.sh"
echo ""
echo "  Quick test (ROS 2):"
echo "    source /opt/ros/jazzy/setup.bash"
echo "    ros2 run demo_nodes_cpp talker"
echo ""
