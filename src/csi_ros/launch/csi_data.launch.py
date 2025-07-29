from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='your_package_name',
            executable='your_node_executable',
            name='your_node_name',
        ),
    ])