#!/usr/bin/env sh

function setup_manager {
    # Install mosquitto MQTT broker
    sudo apt-add-repository ppa:mosquitto-dev/mosquitto-ppa -y > /dev/null 2>&1
    echo "Updating packages"
    sudo apt-get update --quiet=3
    echo "Installing mosquitto"
    sudo apt install -y mosquitto --quiet
    
    # Configure mosquitto and open port
    echo "Configuring mosquitto"
    sudo cp mosquitto.conf /etc/mosquitto/mosquitto.conf
    sudo systemctl restart mosquitto.service
    sudo ufw allow proto tcp to any port 1883
    
    # Install python requirements
    echo "Installing python packages"
    pip3 install torchvision torch pillow paho-mqtt --quiet
    
    # Install a service
    echo "Installing systemd service"
    sudo cp edge_cloud.service /etc/systemd/system/
    sudo systemctl start edge_cloud
    sudo systemctl enable edge_cloud
    
    # Create empty results file
    touch out.csv
    echo "Setup done"
}

setup_manager
