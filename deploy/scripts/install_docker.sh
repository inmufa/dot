#!/usr/bin/env bash
# Installs Docker Engine (not Docker Desktop) from Docker's apt repo, per docs.docker.com/engine/install/ubuntu.
set -euo pipefail

for pkg in docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc; do
  sudo apt-get remove -y "$pkg" 2>/dev/null || true
done

sudo apt-get update
sudo apt-get install -y ca-certificates curl mesa-vulkan-drivers vulkan-tools
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

codename="$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")"
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${codename}
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# GPU access for containers and the docker CLI without sudo
sudo usermod -aG docker,render,video "$USER"
sudo systemctl enable --now docker

echo "Done. Log out and back in (or run: newgrp docker) for group changes."
docker --version
