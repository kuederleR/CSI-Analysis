#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /opt/ros2-csi-msgs/install/setup.bash
cd /csi_ros
colcon build --install-base install
source /csi_ros/install/setup.bash
ros2 launch csi_ros csi_data.launch.py