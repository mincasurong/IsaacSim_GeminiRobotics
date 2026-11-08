#!/usr/bin/env bash
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
BOLD='\033[1m'

MUJOCO_WS="${HOME}/mujoco_ws"
CATKIN_WS="${HOME}/catkin_ws"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "${SCRIPT_DIR}/../stamp" ]; then
    REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
elif [ -n "${ISAAC_GEMINI_REPO:-}" ] && [ -d "${ISAAC_GEMINI_REPO}" ]; then
    REPO_ROOT="${ISAAC_GEMINI_REPO}"
else
    REPO_ROOT="${MUJOCO_WS}"
fi

provision_mujoco_workspace() {
    mkdir -p "${MUJOCO_WS}/scenes" "${MUJOCO_WS}/mjcf" "${MUJOCO_WS}/bddl" "${MUJOCO_WS}/datasets" "${MUJOCO_WS}/logs"
    if [ -f "${REPO_ROOT}/wsl_ws/src/isaac_ros2_control/isaac_ros2_control/mujoco_env.py" ]; then
        cp "${REPO_ROOT}/wsl_ws/src/isaac_ros2_control/isaac_ros2_control/mujoco_env.py" "${MUJOCO_WS}/mujoco_env.py"
        if [ -d "${CATKIN_WS}/src/isaac_ros2_control/isaac_ros2_control" ]; then
            cp "${REPO_ROOT}/wsl_ws/src/isaac_ros2_control/isaac_ros2_control/mujoco_env.py" "${CATKIN_WS}/src/isaac_ros2_control/isaac_ros2_control/mujoco_env.py"
        fi
    fi
    if [ "${REPO_ROOT}" != "${MUJOCO_WS}" ] && [ -f "${REPO_ROOT}/wsl_ws/mujoco_ws/run_mujoco_scene.py" ]; then
        cp "${REPO_ROOT}/wsl_ws/mujoco_ws/run_mujoco_scene.py" "${MUJOCO_WS}/scenes/run_mujoco_scene.py"
        sed -i 's/\r$//' "${MUJOCO_WS}/scenes/run_mujoco_scene.py"
        chmod +x "${MUJOCO_WS}/scenes/run_mujoco_scene.py"
    fi
    if [ "${REPO_ROOT}" != "${MUJOCO_WS}" ] && [ -f "${REPO_ROOT}/wsl_ws/launcher_mujoco.sh" ]; then
        cp "${REPO_ROOT}/wsl_ws/launcher_mujoco.sh" "${MUJOCO_WS}/launcher_mujoco.sh"
        sed -i 's/\r$//' "${MUJOCO_WS}/launcher_mujoco.sh"
        chmod +x "${MUJOCO_WS}/launcher_mujoco.sh"
    fi
    export PYTHONPATH="${MUJOCO_WS}:${CATKIN_WS}/src/isaac_ros2_control:${CATKIN_WS}/src/isaac_ros2_control/isaac_ros2_control:${PYTHONPATH:-}"
    if [ -f "${MUJOCO_WS}/scenes/run_mujoco_scene.py" ]; then
        python3 "${MUJOCO_WS}/scenes/run_mujoco_scene.py" --export-ws "${MUJOCO_WS}" >/dev/null
    fi
}

source_ros2_env() {
    if [ -f "/opt/ros/jazzy/setup.bash" ]; then
        source /opt/ros/jazzy/setup.bash
    fi
    if [ -f "${CATKIN_WS}/install/setup.bash" ]; then
        source "${CATKIN_WS}/install/setup.bash"
    fi
    export PYTHONPATH="${MUJOCO_WS}:${CATKIN_WS}/src/isaac_ros2_control/isaac_ros2_control:${PYTHONPATH:-}"
}

launch_mode_full_stack() {
    local MODE_ID="$1"
    local VIEWER_FLAG="${2:-true}"
    echo -e "\n${GREEN}[1/2] Stopping stale ROS 2 / MuJoCo processes...${NC}"
    pkill -f '[m]ujoco_sim_node' 2>/dev/null || true
    pkill -f '[r]un_mujoco_scene' 2>/dev/null || true
    pkill -f '[c]onveyor_dual_controller' 2>/dev/null || true
    pkill -f '[m]ulti_robot_controller' 2>/dev/null || true
    pkill -f '[g]emini_robotics_node' 2>/dev/null || true
    pkill -f '[c]onveyor_gemini_node' 2>/dev/null || true
    pkill -f '[r]osbridge' 2>/dev/null || true
    source_ros2_env

    echo -e "${GREEN}[2/2] Starting WSL2-Native MuJoCo Workcell (Mode ${MODE_ID}) + ROS 2 Controllers + rosbridge (:9090)...${NC}"
    ros2 launch rosbridge_server rosbridge_websocket_launch.xml >/tmp/mujoco_rosbridge.log 2>&1 &
    if [ "${MODE_ID}" = "1" ]; then
        python3 "${MUJOCO_WS}/scenes/run_mujoco_scene.py" --mode 1 $( [ "${VIEWER_FLAG}" = "true" ] && echo "--viewer" ) &
        ros2 launch isaac_ros2_control gemini_controller.launch.py
    else
        ros2 launch isaac_ros2_control mujoco_workcell.launch.py workcell_mode:="${MODE_ID}" enable_viewer:="${VIEWER_FLAG}"
    fi
}

echo -e "${BOLD}=========================================================================${NC}"
echo -e "${BOLD}  WSL2-Native MuJoCo 3.17 + LIBERO / robomimic + STAMP Unified Launcher  ${NC}"
echo -e "${BOLD}=========================================================================${NC}"

provision_mujoco_workspace
echo -e "${GREEN}[INFO] WSL2 MuJoCo workspace synced at: ${MUJOCO_WS}${NC}"
echo -e "${CYAN}       MJCF Scenes : ${MUJOCO_WS}/mjcf/mode{1,2,3}_*.xml${NC}"
echo -e "${CYAN}       LIBERO BDDL : ${MUJOCO_WS}/bddl/mode{1,2,3}_*.bddl${NC}"
echo -e "${CYAN}       Datasets    : ${MUJOCO_WS}/datasets/${NC}"

if [ -n "${1:-}" ]; then
    CHOICE="$1"
else
    echo ""
    echo -e "${CYAN}=========================================================================${NC}"
    echo -e "${CYAN}  Select a WSL2 MuJoCo Option (No Windows Isaac Sim Required):           ${NC}"
    echo -e "${CYAN}=========================================================================${NC}"
    echo -e "  ${BOLD}1)${NC} Mode 1: Three FR3 Robot Tower (MuJoCo + ROS 2 + Gemini VLA)"
    echo -e "  ${BOLD}2)${NC} Mode 2: Dual FR3 Collaboration — Conveyor & LongBar (MuJoCo + ROS 2)"
    echo -e "  ${BOLD}3)${NC} Mode 3: EFE Deformable Basket, Asymmetric Bracket & SDL Vial (MuJoCo)"
    echo -e "  ${BOLD}4)${NC} Run Standalone MuJoCo 3D Viewer Only (Mode 3 Interactive Window)"
    echo -e "  ${BOLD}5)${NC} Run STAMP + Embodied First Exam (EFE) Benchmark & Self-Tests"
    echo -e "  ${BOLD}6)${NC} Export LIBERO BDDL & robomimic Dataset to ~/mujoco_ws/datasets"
    echo -e "  ${BOLD}0)${NC} Exit"
    echo -e "${CYAN}=========================================================================${NC}"
    read -p "Enter your choice (0-6): " CHOICE
fi

case "${CHOICE}" in
    1)
        launch_mode_full_stack 1 true
        ;;
    2)
        launch_mode_full_stack 2 true
        ;;
    3)
        launch_mode_full_stack 3 true
        ;;
    4)
        source_ros2_env
        MODE_SEL="${2:-3}"
        echo -e "\n${GREEN}[SIMULATOR] Launching MuJoCo 3D Simulator + ROS 2 Bridge (Mode ${MODE_SEL})...${NC}"
        echo -e "${CYAN}Now you can run 'bash ~/catkin_ws/bringup.bash' (or click Start in Web GUI) in another terminal!${NC}"
        python3 "${MUJOCO_WS}/scenes/run_mujoco_scene.py" --mode "${MODE_SEL}" --viewer
        ;;
    5)
        source_ros2_env
        echo -e "\n${GREEN}[TEST] Running MuJoCo Modes 1, 2, 3 Self-Tests & Embodied First Exam Evaluation...${NC}"
        python3 "${MUJOCO_WS}/scenes/run_mujoco_scene.py" --mode 1 --test
        python3 "${MUJOCO_WS}/scenes/run_mujoco_scene.py" --mode 2 --test
        python3 "${MUJOCO_WS}/scenes/run_mujoco_scene.py" --mode 3 --test
        python3 "${MUJOCO_WS}/scenes/run_mujoco_scene.py" --efe-eval
        ;;
    6)
        source_ros2_env
        python3 "${MUJOCO_WS}/scenes/run_mujoco_scene.py" --export-ws "${MUJOCO_WS}"
        ;;
    0)
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice: ${CHOICE}${NC}"
        exit 1
        ;;
esac
