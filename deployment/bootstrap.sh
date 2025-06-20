#!/bin/bash
exec > /home/ubuntu/bootstrap.log 2>&1
set -e

# Install required tools
sudo apt update && sudo apt install -y \
    ca-certificates curl gnupg lsb-release unzip git

# Add Docker’s official GPG key
sudo mkdir -m 0755 -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker apt repo
echo \
  "deb [arch=$(dpkg --print-architecture) \
  signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install latest Docker Engine and CLI
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add user to docker group (take effect after SSH)
sudo usermod -aG docker ubuntu

# Enable Docker on boot
sudo systemctl enable docker
sudo systemctl start docker

sudo apt install -y python3 python3-pip

cd /home/ubuntu
git clone https://github.com/sanjeevmax6/quant-dev-trial-sanjeev.git
sudo chown -R ubuntu:ubuntu quant-dev-trial-sanjeev

cd quant-dev-trial-sanjeev
pip3 install -r requirements.txt

echo "Bootstrap complete. SSH into the instance and run:"
echo " cd ~/quant-dev-trial-sanjeev && docker compose up -d"
