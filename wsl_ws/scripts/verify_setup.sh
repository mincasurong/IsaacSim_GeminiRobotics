#!/usr/bin/env bash
###############################################################################
# Verify Setup — Robotics Development Environment Health Check
#
# Runs automated checks across all setup phases and reports pass/fail status.
#
# Usage:  chmod +x scripts/verify_setup.sh && ./scripts/verify_setup.sh
###############################################################################
set -uo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
BOLD='\033[1m'

PASS=0; FAIL=0; WARN=0

check_pass() { echo -e "  ${GREEN}✔ PASS${NC}  $*"; ((PASS++)); }
check_fail() { echo -e "  ${RED}✘ FAIL${NC}  $*"; ((FAIL++)); }
check_warn() { echo -e "  ${YELLOW}! WARN${NC}  $*"; ((WARN++)); }

echo ""
echo -e "${BOLD}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   Isaac Sim + Isaac ROS Environment — Health Check            ║${NC}"
echo -e "${BOLD}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

###############################################################################
echo -e "${CYAN}── Phase 1: System Base ──${NC}"
###############################################################################

# OS check
if [ -f /etc/os-release ]; then
    OS_ID=$(. /etc/os-release && echo "$ID")
    OS_VER=$(. /etc/os-release && echo "$VERSION_ID")
    if [ "$OS_ID" = "ubuntu" ] && [ "$OS_VER" = "24.04" ]; then
        check_pass "Ubuntu 24.04 (Noble Numbat)"
    else
        check_warn "OS: ${OS_ID} ${OS_VER} (expected Ubuntu 24.04)"
    fi
else
    check_fail "Cannot determine OS"
fi

# WSL2 check
if grep -qi "microsoft" /proc/version 2>/dev/null; then
    check_pass "WSL2 environment detected"
else
    check_warn "Not running in WSL2"
fi

# Locale
if locale 2>/dev/null | grep -q "UTF-8"; then
    check_pass "UTF-8 locale configured"
else
    check_warn "Locale may not be UTF-8"
fi

# Build tools
for cmd in gcc g++ cmake git curl wget; do
    if command -v "$cmd" &>/dev/null; then
        check_pass "$cmd available"
    else
        check_fail "$cmd not found"
    fi
done

# Git LFS
if git lfs version &>/dev/null; then
    check_pass "Git LFS installed: $(git lfs version | head -1)"
else
    check_fail "Git LFS not installed"
fi

# Python
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    check_pass "Python3: ${PY_VER}"
else
    check_fail "Python3 not found"
fi

###############################################################################
echo ""
echo -e "${CYAN}── Phase 1.5: NVIDIA GPU ──${NC}"
###############################################################################

if command -v nvidia-smi &>/dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
    DRIVER_VER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
    VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")

    check_pass "GPU: ${GPU_NAME}"
    check_pass "Driver: ${DRIVER_VER}"
    check_pass "VRAM: ${VRAM}"

    # Check VRAM >= 8GB
    VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
    if [ -n "$VRAM_MB" ] && [ "$VRAM_MB" -ge 8000 ]; then
        check_pass "VRAM ≥ 8GB (Isaac Sim minimum met)"
    else
        check_warn "VRAM < 8GB — Isaac Sim may struggle"
    fi
else
    check_fail "nvidia-smi not available (NVIDIA driver not passed through)"
fi

###############################################################################
echo ""
echo -e "${CYAN}── Phase 2: Docker + NVIDIA Container Toolkit ──${NC}"
###############################################################################

if command -v docker &>/dev/null; then
    check_pass "Docker: $(docker --version 2>/dev/null)"
else
    check_fail "Docker not installed"
fi

if docker info &>/dev/null 2>&1; then
    check_pass "Docker daemon is running"
else
    check_warn "Docker daemon not accessible (try: sudo service docker start)"
fi

if groups "$USER" 2>/dev/null | grep -qw docker; then
    check_pass "User '$USER' in docker group"
else
    check_warn "User '$USER' not in docker group"
fi

if command -v nvidia-ctk &>/dev/null; then
    check_pass "NVIDIA Container Toolkit installed"
else
    check_fail "NVIDIA Container Toolkit (nvidia-ctk) not found"
fi

# GPU in Docker test (quick, may fail if daemon not ready)
if docker info &>/dev/null 2>&1; then
    if docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi &>/dev/null 2>&1; then
        check_pass "GPU accessible inside Docker containers"
    else
        check_warn "GPU Docker test failed (try: docker run --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi)"
    fi
fi

###############################################################################
echo ""
echo -e "${CYAN}── Phase 3: ROS 2 Jazzy ──${NC}"
###############################################################################

# Source ROS 2 if available
if [ -f /opt/ros/jazzy/setup.bash ]; then
    source /opt/ros/jazzy/setup.bash
    check_pass "ROS 2 Jazzy installed at /opt/ros/jazzy/"

    ROS_DISTRO_VAL=$(printenv ROS_DISTRO 2>/dev/null || echo "")
    if [ "$ROS_DISTRO_VAL" = "jazzy" ]; then
        check_pass "ROS_DISTRO = jazzy"
    else
        check_fail "ROS_DISTRO = ${ROS_DISTRO_VAL} (expected jazzy)"
    fi

    # Check key packages
    for pkg in moveit navigation2 ros2_control rviz2 xacro; do
        if ros2 pkg list 2>/dev/null | grep -q "$pkg"; then
            check_pass "Package: ${pkg}"
        else
            check_warn "Package not found: ${pkg}"
        fi
    done

    # DDS middleware
    RMW_VAL=$(printenv RMW_IMPLEMENTATION 2>/dev/null || echo "not set")
    if [ "$RMW_VAL" = "rmw_fastrtps_cpp" ]; then
        check_pass "RMW_IMPLEMENTATION = rmw_fastrtps_cpp"
    else
        check_warn "RMW_IMPLEMENTATION = ${RMW_VAL} (recommend rmw_fastrtps_cpp for Isaac Sim)"
    fi

    # Domain ID
    DOMAIN_VAL=$(printenv ROS_DOMAIN_ID 2>/dev/null || echo "not set")
    check_pass "ROS_DOMAIN_ID = ${DOMAIN_VAL}"
else
    check_fail "ROS 2 Jazzy not found at /opt/ros/jazzy/"
fi

###############################################################################
echo ""
echo -e "${CYAN}── Phase 4: Isaac ROS Workspace ──${NC}"
###############################################################################

ISAAC_ROS_WS="${HOME}/workspaces/isaac_ros-dev"

if [ -d "${ISAAC_ROS_WS}/src" ]; then
    check_pass "Isaac ROS workspace exists: ${ISAAC_ROS_WS}"

    REPO_COUNT=$(ls -d "${ISAAC_ROS_WS}/src"/*/ 2>/dev/null | wc -l)
    check_pass "Repositories cloned: ${REPO_COUNT}"

    if [ -f "${ISAAC_ROS_WS}/src/isaac_ros_common/scripts/run_dev.sh" ]; then
        check_pass "run_dev.sh available"
    else
        check_fail "isaac_ros_common/scripts/run_dev.sh not found"
    fi
else
    check_warn "Isaac ROS workspace not found at ${ISAAC_ROS_WS}"
fi

###############################################################################
echo ""
echo -e "${CYAN}── Phase 5: DDS Bridge Configuration ──${NC}"
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FASTDDS_FILE="${SCRIPT_DIR}/../config/fastdds_profile.xml"

if [ -f "$FASTDDS_FILE" ]; then
    check_pass "FastDDS profile exists: ${FASTDDS_FILE}"
else
    check_warn "FastDDS profile not found (run setup_ros2_bridge_config.sh)"
fi

FASTDDS_ENV=$(printenv FASTRTPS_DEFAULT_PROFILES_FILE 2>/dev/null || echo "not set")
if [ "$FASTDDS_ENV" != "not set" ] && [ -f "$FASTDDS_ENV" ]; then
    check_pass "FASTRTPS_DEFAULT_PROFILES_FILE = ${FASTDDS_ENV}"
else
    check_warn "FASTRTPS_DEFAULT_PROFILES_FILE not set or file missing"
fi

###############################################################################
# Summary
###############################################################################
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}✔ PASS: ${PASS}${NC}   ${RED}✘ FAIL: ${FAIL}${NC}   ${YELLOW}! WARN: ${WARN}${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo -e "  ${GREEN}All critical checks passed!${NC}"
    echo ""
    echo "  Next steps:"
    echo "    1. Install Isaac Sim 4.5 on Windows (see docs/ISAAC_SIM_WINDOWS_SETUP.md)"
    echo "    2. Launch Isaac Sim with ROS2 bridge enabled"
    echo "    3. Run: ros2 topic list  (from WSL2 to verify bridge)"
    echo ""
elif [ "$FAIL" -le 2 ]; then
    echo -e "  ${YELLOW}Minor issues detected. Review FAIL items above.${NC}"
else
    echo -e "  ${RED}Multiple failures. Re-run the setup scripts for failed phases.${NC}"
fi
