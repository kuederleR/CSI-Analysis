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
    && curl -fsSL https://raw.githubusercontent.com/kuederleR/ros2-csi-msgs/refs/heads/main/install.sh | bash \
    && rm -rf /var/lib/apt/lists/*

COPY py-requirements.txt /tmp/py-requirements.txt

RUN pip3 install -r /tmp/py-requirements.txt && \
    rm /tmp/py-requirements.txt

WORKDIR /ros2_ws

CMD ["bash"]