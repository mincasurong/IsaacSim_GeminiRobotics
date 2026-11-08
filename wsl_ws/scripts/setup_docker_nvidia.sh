#!/usr/bin/env bash
###############################################################################
# Phase 2: Docker Engine + NVIDIA Container Toolkit
#
# Installs Docker via official APT (NOT snap) and configures the NVIDIA
# Container Toolkit for GPU-accelerated containers (Isaac ROS, CUDA, etc.).
#
# Usage:  chmod +x scripts/setup_docker_nvidia.sh && ./scripts/setup_docker_nvidia.sh
###############################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/../logs/setup_docker_nvidia.log"
mkdir -p "$(dirname "$LOG_FILE")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[$(date '+%H:%M:%S')]${NC} $*" | tee -a "$LOG_FILE"; }
ok()   { echo -e "${GREEN}[✔]${NC} $*" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[!]${NC} $*" | tee -a "$LOG_FILE"; }
fail() { echo -e "${RED}[✘]${NC} $*" | tee -a "$LOG_FILE"; exit 1; }

###############################################################################
# 0. Check if Docker Desktop is managing Docker (skip engine install if so)
###############################################################################
DOCKER_DESKTOP=false
if docker info 2>/dev/null | grep -qi "docker desktop"; then
    warn "Docker Desktop detected — skipping Docker Engine installation."
    warn "Ensure WSL Integration is enabled in Docker Desktop settings."
    DOCKER_DESKTOP=true
fi

###############################################################################
# 1. Remove conflicting Docker packages (snap, old versions)
###############################################################################
if [ "$DOCKER_DESKTOP" = false ]; then
    log "=== Phase 2.1: Removing Conflicting Docker Packages ==="

    # Remove snap docker if present (snap blocks GPU access)
    if snap list docker 2>/dev/null; then
        warn "Removing snap Docker (incompatible with GPU passthrough)..."
        sudo snap remove docker 2>/dev/null || true
    fi

    # Remove old/conflicting packages
    for pkg in docker.io docker-doc docker-compose docker-compose-v2 \
               podman-docker containerd runc; do
        sudo apt-get remove -y -qq "$pkg" 2>/dev/null || true
    done

    ok "Conflicting packages removed"

    ###########################################################################
    # 2. Install Docker Engine (Official APT)
    ###########################################################################
    log "=== Phase 2.2: Installing Docker Engine ==="

    # Add Docker's official GPG key
    sudo install -m 0755 -d /etc/apt/keyrings
    if [ ! -f /etc/apt/keyrings/docker.asc ]; then
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
            sudo tee /etc/apt/keyrings/docker.asc > /dev/null
        sudo chmod a+r /etc/apt/keyrings/docker.asc
    fi

    # Add Docker APT repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
      https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update -qq

    # Install Docker Engine, CLI, plugins
    sudo apt-get install -y -qq \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin \
        2>&1 | tail -5 | tee -a "$LOG_FILE"

    ok "Docker Engine installed"

    ###########################################################################
    # 3. Configure Docker group
    ###########################################################################
    log "=== Phase 2.3: Configuring Docker User Group ==="

    if ! groups "$USER" | grep -qw docker; then
        sudo usermod -aG docker "$USER"
        warn "Added $USER to 'docker' group — you may need to log out/in or run 'newgrp docker'"
    else
        ok "User $USER already in docker group"
    fi

    ###########################################################################
    # 4. Start Docker daemon
    ###########################################################################
    log "=== Phase 2.4: Starting Docker Daemon ==="

    # WSL2 may use systemd or init — handle both
    if command -v systemctl &>/dev/null && systemctl is-system-running &>/dev/null 2>&1; then
        sudo systemctl enable docker
        sudo systemctl start docker
        ok "Docker started via systemd"
    else
        sudo service docker start 2>/dev/null || true
        ok "Docker started via service"
    fi
fi

###############################################################################
# 5. Install NVIDIA Container Toolkit
###############################################################################
log "=== Phase 2.5: Installing NVIDIA Container Toolkit ==="

# Add NVIDIA Container Toolkit repository
if [ ! -f /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg ]; then
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
        sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
fi

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null

sudo apt-get update -qq
sudo apt-get install -y -qq nvidia-container-toolkit 2>&1 | tail -3 | tee -a "$LOG_FILE"

ok "NVIDIA Container Toolkit installed"

###############################################################################
# 6. Configure Docker Runtime for NVIDIA
###############################################################################
log "=== Phase 2.6: Configuring NVIDIA Docker Runtime ==="

if [ "$DOCKER_DESKTOP" = false ]; then
    sudo nvidia-ctk runtime configure --runtime=docker 2>&1 | tee -a "$LOG_FILE"

    # Restart Docker to apply runtime changes
    if command -v systemctl &>/dev/null && systemctl is-system-running &>/dev/null 2>&1; then
        sudo systemctl restart docker
    else
        sudo service docker restart 2>/dev/null || true
    fi

    ok "NVIDIA runtime configured for Docker"
else
    warn "Docker Desktop detected — NVIDIA runtime should be auto-configured."
    warn "If GPU containers fail, check Docker Desktop → Settings → Docker Engine"
    warn "and ensure \"default-runtime\": \"nvidia\" is set."
fi

###############################################################################
# 7. Verification
###############################################################################
log "=== Phase 2.7: Verifying Docker + GPU Setup ==="

echo ""
log "Testing Docker..."
if docker run --rm hello-world 2>&1 | grep -q "Hello from Docker"; then
    ok "Docker is working correctly"
else
    # Might fail if user isn't in docker group yet in this session
    warn "Docker test failed — try: newgrp docker && docker run --rm hello-world"
fi

echo ""
log "Testing GPU access in Docker container..."
if docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi 2>&1 | grep -q "NVIDIA"; then
    ok "GPU accessible inside Docker containers!"
    echo ""
    docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi 2>&1 | head -20 | tee -a "$LOG_FILE"
else
    warn "GPU Docker test failed. Possible causes:"
    warn "  1. Need to log out/in for docker group (run: newgrp docker)"
    warn "  2. NVIDIA Container Toolkit not properly configured"
    warn "  3. Docker Desktop needs 'Use the WSL 2 based engine' enabled"
fi

###############################################################################
# Summary
###############################################################################
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Phase 2 Complete: Docker + NVIDIA Container Toolkit Ready${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Docker version: $(docker --version 2>/dev/null || echo 'N/A')"
echo "  NVIDIA CTK:     $(nvidia-ctk --version 2>/dev/null || echo 'N/A')"
echo ""
echo "  Next step: Run ./scripts/setup_ros2_jazzy.sh (Phase 3)"
echo ""
