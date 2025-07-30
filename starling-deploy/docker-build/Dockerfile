# ROS2 Humble base image
FROM ros:humble

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-pip \
        python3-colcon-common-extensions \
        ros-humble-rmw-fastrtps-cpp \
        ros-humble-ros-base \
        ros-humble-ros2launch \
        ros-humble-rclcpp \
    && curl -fsSL https://raw.githubusercontent.com/kuederleR/ros2-csi-msgs/refs/heads/main/install.sh | bash \
    && rm -rf /var/lib/apt/lists/*

COPY py-requirements.txt /tmp/py-requirements.txt
RUN pip3 install -r /tmp/py-requirements.txt && rm /tmp/py-requirements.txt

ARG PX4_MSGS_BRANCH="release/1.14"
RUN git clone --branch ${PX4_MSGS_BRANCH} https://github.com/PX4/px4_msgs.git external_packages/src/px4_msgs


WORKDIR /csi_ros

COPY exec/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]