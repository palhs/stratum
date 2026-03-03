#!/usr/bin/env bash
# =============================================================================
# scripts/provision-vps.sh — One-time Docker installation on Ubuntu VPS
#
# Purpose: Install Docker CE + Docker Compose plugin on a fresh Ubuntu server
#          using Docker's official APT repository.
#
# Usage:   bash scripts/provision-vps.sh
#
# Tested: Ubuntu 22.04 LTS, Ubuntu 24.04 LTS
#
# NOTE: Run as a user with sudo access, NOT as root.
#       After running, log out and back in for the docker group to take effect.
# =============================================================================

set -euo pipefail

echo "================================================="
echo "Stratum VPS Provisioning — Docker CE Installation"
echo "================================================="
echo ""

# ---------------------------------------------------------------------------
# Step 1: Remove unofficial Docker packages (Ubuntu ships docker.io which is
# outdated and does not include the compose plugin)
# ---------------------------------------------------------------------------
echo "[1/5] Removing unofficial Docker packages (if present)..."
sudo apt-get remove -y \
    docker \
    docker-engine \
    docker.io \
    containerd \
    runc \
    docker-compose \
    2>/dev/null || true

echo "  Done."

# ---------------------------------------------------------------------------
# Step 2: Install prerequisites for Docker's APT repository
# ---------------------------------------------------------------------------
echo "[2/5] Installing APT prerequisites..."
sudo apt-get update
sudo apt-get install -y \
    ca-certificates \
    curl

echo "  Done."

# ---------------------------------------------------------------------------
# Step 3: Add Docker's official GPG key and APT repository
# ---------------------------------------------------------------------------
echo "[3/5] Adding Docker's official GPG key and APT repository..."
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
echo "  Done."

# ---------------------------------------------------------------------------
# Step 4: Install Docker CE and the Compose plugin
# ---------------------------------------------------------------------------
echo "[4/5] Installing Docker CE, CLI, containerd, buildx plugin, compose plugin..."
sudo apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

echo "  Done."

# ---------------------------------------------------------------------------
# Step 5: Add current user to the docker group (avoids needing sudo for all
# docker commands). Requires logout/login to take effect.
# ---------------------------------------------------------------------------
echo "[5/5] Adding ${USER} to docker group..."
sudo usermod -aG docker "${USER}"
echo "  Done."

echo ""
echo "================================================="
echo "Installation complete."
echo ""
echo "IMPORTANT: Log out and back in for docker group"
echo "membership to take effect, then verify:"
echo ""
echo "  docker compose version"
echo "  docker run hello-world"
echo "================================================="
echo ""

# Verify Docker is installed (runs as root via sudo until re-login)
echo "Current Docker version (sudo required until re-login):"
sudo docker compose version
