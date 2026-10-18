#!/usr/bin/env bash
###############################################################################
# Phase 1: WSL2 Ubuntu 24.04 — Base System Preparation
#
# Sets up locale, essential build tools, Python environment, and verifies
# NVIDIA GPU passthrough from the Windows host.
#
# Usage:  chmod +x scripts/setup_wsl2_base.sh && ./scripts/setup_wsl2_base.sh
###############################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/../logs/setup_wsl2_base.log"
mkdir -p "$(dirname "$LOG_FILE")"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date '+%H:%M:%S')]${NC} $*" | tee -a "$LOG_FILE"; }
ok()   { echo -e "${GREEN}[✔]${NC} $*" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[!]${NC} $*" | tee -a "$LOG_FILE"; }
fail() { echo -e "${RED}[✘]${NC} $*" | tee -a "$LOG_FILE"; exit 1; }

###############################################################################
# 1. Locale Configuration
###############################################################################
log "=== Phase 1.1: Configuring Locale ==="

sudo apt-get update -qq && sudo apt-get install -y -qq locales > /dev/null 2>&1
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

ok "Locale set to en_US.UTF-8"

###############################################################################
# 2. System Update
###############################################################################
log "=== Phase 1.2: System Update ==="

sudo apt-get update -qq
sudo apt-get full-upgrade -y -qq 2>&1 | tail -5 | tee -a "$LOG_FILE"

ok "System packages updated"

###############################################################################
# 3. Essential Build Tools & Utilities
###############################################################################
log "=== Phase 1.3: Installing Build Tools & Utilities ==="

PACKAGES=(
    # Build essentials
    build-essential
    cmake
    pkg-config
    # Version control
    git
    git-lfs
    # Network / download
    curl
    wget
    gnupg
    ca-certificates
    # System utilities
    lsb-release
    software-properties-common
    apt-transport-https
    # Compression
    unzip
    zip
    tar
    # Editors / tools
    vim
    htop
    tree
    # X11 forwarding (for RViz, rqt from WSL2)
    x11-apps
    mesa-utils
)

sudo apt-get install -y -qq "${PACKAGES[@]}" 2>&1 | tail -5 | tee -a "$LOG_FILE"

# Initialize Git LFS
git lfs install --skip-repo 2>/dev/null || true

ok "Build tools and utilities installed (${#PACKAGES[@]} packages)"

###############################################################################
# 4. Python 3 Environment
###############################################################################
log "=== Phase 1.4: Python Environment ==="

# Ubuntu 24.04 ships with Python 3.12; install pip and venv support
sudo apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-setuptools \
    python3-wheel \
    2>&1 | tail -3 | tee -a "$LOG_FILE"

PYTHON_VER=$(python3 --version 2>&1)
ok "Python installed: ${PYTHON_VER}"

# Also install Python 3.10 for Isaac Sim 4.5 compatibility (pip install on Windows)
# This is optional — Isaac Sim runs on Windows, but useful for Isaac Lab scripts
if ! command -v python3.10 &>/dev/null; then
    log "Installing Python 3.10 (for Isaac Lab / Isaac Sim script compatibility)..."
    sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3.10 python3.10-venv python3.10-dev 2>&1 | tail -3 | tee -a "$LOG_FILE"
    ok "Python 3.10 installed for Isaac Sim compatibility"
else
    ok "Python 3.10 already available"
fi

###############################################################################
# 5. NVIDIA GPU Verification
###############################################################################
log "=== Phase 1.5: NVIDIA GPU Verification ==="

if command -v nvidia-smi &>/dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null || echo "")
    if [ -n "$GPU_INFO" ]; then
        ok "NVIDIA GPU detected: ${GPU_INFO}"

        # Check VRAM (need at least 8GB for Isaac Sim)
        VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
        if [ -n "$VRAM_MB" ] && [ "$VRAM_MB" -ge 8000 ]; then
            ok "GPU VRAM: ${VRAM_MB} MiB (≥8GB requirement met)"
        else
            warn "GPU VRAM: ${VRAM_MB} MiB — Isaac Sim recommends 8GB+ (11GB+ preferred)"
        fi

        # Show full nvidia-smi for reference
        echo "" | tee -a "$LOG_FILE"
        nvidia-smi | tee -a "$LOG_FILE"
    else
        fail "nvidia-smi found but could not query GPU. Check Windows NVIDIA driver."
    fi
else
    fail "nvidia-smi not found. Ensure NVIDIA GPU driver is installed on Windows host."
fi

###############################################################################
# 6. Verify WSL2 (not WSL1)
###############################################################################
log "=== Phase 1.6: WSL Version Check ==="

if grep -qi "microsoft" /proc/version 2>/dev/null; then
    if [ -d "/usr/lib/wsl" ]; then
        ok "Running on WSL2 (confirmed)"
    else
        warn "Running on WSL but version uncertain — ensure WSL2 is enabled"
    fi
else
    warn "Not running under WSL — this script is designed for WSL2 Ubuntu 24.04"
fi

# Check Ubuntu version
UBUNTU_VER=$(lsb_release -rs 2>/dev/null || echo "unknown")
if [ "$UBUNTU_VER" = "24.04" ]; then
    ok "Ubuntu ${UBUNTU_VER} (Noble Numbat) confirmed"
else
    warn "Expected Ubuntu 24.04, found ${UBUNTU_VER}"
fi

###############################################################################
# Summary
###############################################################################
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Phase 1 Complete: WSL2 Base System Ready${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Next step: Run ./scripts/setup_docker_nvidia.sh (Phase 2)"
echo ""
