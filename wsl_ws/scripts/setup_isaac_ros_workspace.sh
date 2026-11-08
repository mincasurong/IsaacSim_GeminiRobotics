#!/usr/bin/env bash
###############################################################################
# Phase 4: Isaac ROS 4.x Workspace Setup
#
# Sets up the Isaac ROS development workspace using NVIDIA's Docker-based
# workflow. Clones core infrastructure and key robotics packages.
#
# NOTE: Isaac ROS packages run inside Docker containers managed by run_dev.sh.
#       The workspace is mounted from your host into the container.
#
# Usage:  chmod +x scripts/setup_isaac_ros_workspace.sh && ./scripts/setup_isaac_ros_workspace.sh
###############################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/../logs/setup_isaac_ros_workspace.log"
mkdir -p "$(dirname "$LOG_FILE")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date '+%H:%M:%S')]${NC} $*" | tee -a "$LOG_FILE"; }
ok()   { echo -e "${GREEN}[✔]${NC} $*" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[!]${NC} $*" | tee -a "$LOG_FILE"; }
fail() { echo -e "${RED}[✘]${NC} $*" | tee -a "$LOG_FILE"; exit 1; }

###############################################################################
# Configuration
###############################################################################
ISAAC_ROS_WS="${HOME}/workspaces/isaac_ros-dev"
ISAAC_ROS_SRC="${ISAAC_ROS_WS}/src"
ISAAC_ROS_ORG="https://github.com/NVIDIA-ISAAC-ROS"

# Use a stable release tag if available; fall back to main
# Check https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_common/tags for latest
ISAAC_ROS_TAG="main"

###############################################################################
# 0. Prerequisites Check
###############################################################################
log "=== Phase 4.0: Checking Prerequisites ==="

# Docker
if ! command -v docker &>/dev/null; then
    fail "Docker not found. Run setup_docker_nvidia.sh (Phase 2) first."
fi

# Docker group (can current user run docker without sudo?)
if ! docker info &>/dev/null 2>&1; then
    warn "Cannot connect to Docker. Try: newgrp docker"
    warn "Or ensure Docker is running: sudo service docker start"
fi

# Git LFS
if ! command -v git-lfs &>/dev/null; then
    log "Installing Git LFS..."
    sudo apt-get install -y -qq git-lfs 2>/dev/null
fi
git lfs install --skip-repo 2>/dev/null || true

ok "Prerequisites verified"

###############################################################################
# 1. Create Workspace Structure
###############################################################################
log "=== Phase 4.1: Creating Isaac ROS Workspace ==="

mkdir -p "${ISAAC_ROS_SRC}"
ok "Workspace created at ${ISAAC_ROS_WS}"

###############################################################################
# 2. Clone isaac_ros_common (Core Infrastructure)
###############################################################################
log "=== Phase 4.2: Cloning Isaac ROS Common ==="

cd "${ISAAC_ROS_SRC}"

clone_or_pull() {
    local repo_name="$1"
    local repo_url="${ISAAC_ROS_ORG}/${repo_name}.git"
    local target_dir="${ISAAC_ROS_SRC}/${repo_name}"

    if [ -d "${target_dir}" ]; then
        log "  ${repo_name}: already cloned, pulling latest..."
        cd "${target_dir}"
        git pull --ff-only 2>&1 | tail -2 | tee -a "$LOG_FILE" || true
        cd "${ISAAC_ROS_SRC}"
        ok "  ${repo_name} updated"
    else
        log "  Cloning ${repo_name}..."
        git clone "${repo_url}" "${target_dir}" 2>&1 | tail -3 | tee -a "$LOG_FILE"
        ok "  ${repo_name} cloned"
    fi
}

# Core infrastructure (REQUIRED — contains run_dev.sh, Dockerfiles, etc.)
clone_or_pull "isaac_ros_common"

ok "Isaac ROS Common infrastructure ready"

###############################################################################
# 3. Clone Key Isaac ROS Packages
###############################################################################
log "=== Phase 4.3: Cloning Isaac ROS Packages ==="

# --- Perception ---
log "--- Perception Packages ---"
clone_or_pull "isaac_ros_visual_slam"        # GPU-accelerated Visual SLAM
clone_or_pull "isaac_ros_object_detection"   # RT-DETR, YOLOv8
clone_or_pull "isaac_ros_apriltag"           # Fiducial detection
clone_or_pull "isaac_ros_dnn_inference"      # TensorRT/Triton inference

# --- 3D Reconstruction ---
log "--- 3D Reconstruction ---"
clone_or_pull "isaac_ros_nvblox"             # 3D scene reconstruction, Nav2 costmaps

# --- Manipulation (GPU-accelerated motion planning) ---
log "--- Manipulation ---"
clone_or_pull "isaac_ros_cumotion"           # cuMotion: GPU-accelerated motion planning

# --- Common Messages & Interfaces ---
log "--- Common Packages ---"
clone_or_pull "isaac_ros_nitros"             # NVIDIA accelerated transport (zero-copy)
clone_or_pull "isaac_ros_image_pipeline"     # GPU-accelerated image processing

###############################################################################
# 4. Set Environment Variables
###############################################################################
log "=== Phase 4.4: Configuring Environment ==="

BASHRC_MARKER="# >>> Isaac ROS Workspace >>>"
if ! grep -qF "$BASHRC_MARKER" ~/.bashrc 2>/dev/null; then
    cat >> ~/.bashrc << BASHRC_BLOCK

${BASHRC_MARKER}
export ISAAC_ROS_WS=${ISAAC_ROS_WS}

# Alias to launch Isaac ROS dev container
alias irosdev='cd \${ISAAC_ROS_WS}/src/isaac_ros_common && ./scripts/run_dev.sh -d \${ISAAC_ROS_WS}'
# <<< Isaac ROS Workspace <<<
BASHRC_BLOCK
    ok "Environment variables added to ~/.bashrc"
else
    ok "Isaac ROS environment already in ~/.bashrc"
fi

export ISAAC_ROS_WS="${ISAAC_ROS_WS}"

###############################################################################
# 5. Workspace Summary
###############################################################################
log "=== Phase 4.5: Workspace Contents ==="

echo "" | tee -a "$LOG_FILE"
echo "Packages cloned into ${ISAAC_ROS_SRC}:" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

for dir in "${ISAAC_ROS_SRC}"/*/; do
    if [ -d "$dir" ]; then
        pkg_name=$(basename "$dir")
        echo "  📦 ${pkg_name}" | tee -a "$LOG_FILE"
    fi
done

echo "" | tee -a "$LOG_FILE"

###############################################################################
# 6. Test Container Launch (Optional)
###############################################################################
log "=== Phase 4.6: Container Launch Test ==="

RUN_DEV="${ISAAC_ROS_SRC}/isaac_ros_common/scripts/run_dev.sh"

if [ -f "$RUN_DEV" ]; then
    ok "run_dev.sh found at: ${RUN_DEV}"
    echo ""
    warn "To launch the Isaac ROS development container, run:"
    echo ""
    echo "  cd ${ISAAC_ROS_SRC}/isaac_ros_common"
    echo "  ./scripts/run_dev.sh -d ${ISAAC_ROS_WS}"
    echo ""
    warn "First launch will build Docker images (may take 15-30 minutes)."
    warn "Subsequent launches will be fast."
    echo ""
    warn "NOTE: Some Isaac ROS packages require Ampere+ GPUs."
    warn "Your RTX 2080 Ti (Turing) may not support all GPU-accelerated features."
    warn "Core functionality (ROS topics, URDF loading, TF) will still work."
else
    warn "run_dev.sh not found — check isaac_ros_common clone"
fi

###############################################################################
# Summary
###############################################################################
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Phase 4 Complete: Isaac ROS Workspace Ready${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Workspace:      ${ISAAC_ROS_WS}"
echo "  Packages:       $(ls -d "${ISAAC_ROS_SRC}"/*/ 2>/dev/null | wc -l) repos cloned"
echo "  Dev Container:  irosdev  (alias to launch)"
echo ""
echo "  ⚠  RTX 2080 Ti Note:"
echo "     Some Isaac ROS GPU-accelerated packages need Ampere+ GPUs."
echo "     Visual SLAM, cuMotion may run in CPU fallback mode."
echo "     ROS interfaces, topics, and descriptions work on all GPUs."
echo ""
echo "  Next step: Install Isaac Sim 4.5 on Windows (see docs/ISAAC_SIM_WINDOWS_SETUP.md)"
echo ""
