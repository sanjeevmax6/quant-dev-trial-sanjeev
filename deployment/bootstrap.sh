#!/bin/bash

exec > /home/ubuntu/bootstrap.log 2>&1
set -e

# Install Docker and Docker Compose
sudo apt update
sudo apt install -y docker.io docker-compose python3 python3-pip git

# Enable Docker for the current user
sudo usermod -aG docker ubuntu

# Clone your project repo
cd /home/ubuntu
git clone https://github.com/sanjeevmax6/quant-dev-trial-sanjeev.git
cd quant-dev-trial-sanjeev

# Install Python requirements
pip3 install -r requirements.txt

# Pull Kafka + Zookeeper containers
docker-compose pull

echo "Bootstrap complete. To test Kafka, run:"
echo "cd ~/quant-dev-trial-sanjeev"
echo "docker-compose up -d"
echo "python3 kafka_producer.py"
echo "python3 backtest.py > output.json"
