#!/bin/bash
set -e

SERVICE_NAME=starling-docker
WORKDIR="$(dirname $(realpath $0))"

# Create systemd service file
cat <<EOF | sudo tee /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=CSI ROS2 Docker Compose Service
After=network-online.target
Requires=network-online.target
Wants=docker.service
After=docker.service

[Service]
Type=simple
WorkingDirectory=$WORKDIR
ExecStartPre=/bin/sleep 5 # Add a 10-second delay here
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd, enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME

echo "Systemd service '$SERVICE_NAME' installed and started."