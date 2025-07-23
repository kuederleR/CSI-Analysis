#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /csi_ros/install/setup.bash
source /opt/ros2-csi-msgs/install/setup.bash
ros2 run csi_ros csi_pub