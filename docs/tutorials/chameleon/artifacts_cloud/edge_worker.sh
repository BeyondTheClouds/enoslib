#!/usr/bin/env sh

# Topic to publish via MQTT with
topic="${1:-edge_data}"
# Max iterations
MAX="${2:-100}"
MOSQUITTO_HOST="${3:-127.0.0.1}"


# Use this function to configure your container as needed
function setup {
    # Sometimes the default DNS fails, so try this instead.
    echo nameserver 8.8.8.8 > /etc/resolv.conf

    # Install mosquitto clients
    apt-get update
    apt-get install software-properties-common
    apt-add-repository ppa:mosquitto-dev/mosquitto-ppa -y
    apt-get update
    apt-get install mosquitto-clients wget -y
    
    # Download a file listing all images (just for this example)
    wget --quiet https://uchicago.box.com/shared/static/8b1ceicgj1ttal6dgv0hpxzi4quy5p84.csv -O /images.csv
}

# Collect and output the name of the sample file to use
function get_sample {
    # This uses the images file from [1] and downloads the images one at a time.
    # If you are using a sensor on this device, modify this function so that it
    # saves the sensor data to some file.
    # 1: https://datadryad.org/stash/dataset/doi:10.5061/dryad.5pt92
    path=$(tail -n +2 /images.csv | shuf -n 1 | cut -d',' -f2 | sed 's/"//g')
    wget --quiet "https://snapshotserengeti.s3.msi.umn.edu/$path" -O data.jpg
    echo "data.jpg"
}

# Process the sample in the file $1 in anyway needed (crop, rotate, etc.)
function preprocess_sample {
    # This function should take the file $1, and run it through any program
    # needed. Output the result back into file $1.
    
    # For the example dataset, there is text on the bottom 100 pixels, and so we crop it out.
    convert -crop 100%x100%+0-100 $1 $1
}

# Check if this sample should be sent to the cloud (using the return code to indicate value)
function precheck_sample {
    true
}

# Send the data in the file $1 to the specified host $MOSQUITTO_HOST.
function send_sample {
  echo "publishing $1"
  mosquitto_pub -h "$MOSQUITTO_HOST" -t "$topic" -f "$1"
}


# The main loop

# First, run setup
setup
echo "Finished setup"
for ((i=1;i<=MAX;i++)); do
  # Wait a small time between samples
  sleep 3
  
  # Get the sample
  filename=$(get_sample)
  echo "Got sample $filename"
  
  # Preprocess the sample, and precheck it
  preprocess_sample $filename
  if precheck_sample $filename; then
    # If it passes, send it to the cloud
    send_sample $filename;
  fi
done