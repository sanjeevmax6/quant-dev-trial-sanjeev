#!/bin/bash

# Updating system and install dependencies
sudo apt update -y
sudo apt install -y openjdk-11-jre-headless python3 python3-pip wget unzip git

# Installing Kafka
cd /opt
sudo wget https://downloads.apache.org/kafka/3.5.1/kafka_2.13-3.5.1.tgz
sudo tar -xzf kafka_2.13-3.5.1.tgz
sudo mv kafka_2.13-3.5.1 kafka
cd kafka

# Start Zookeeper and Kafka as background daemons
bin/zookeeper-server-start.sh -daemon config/zookeeper.properties
sleep 5
bin/kafka-server-start.sh -daemon config/server.properties

# Clone your GitHub repo (replace this URL)
cd /home/ubuntu
git clone https://github.com/sanjeevmax6/quant-dev-trial-sanjeev.git
cd quant-dev-trial-sanjeev

# Install Python requirements
pip3 install -r requirements.txt

# Start Kafka producer and backtest
python3 kafka_producer.py &
sleep 2
python3 backtest.py > output.json
