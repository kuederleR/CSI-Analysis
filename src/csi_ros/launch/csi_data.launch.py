from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='csi_ros',
            executable='csi_pub',
            name='csi_pub',
        ),
        # Node(
        #     package='csi_ros',
        #     executable='static_base_to_wifi_tf',
        #     name='static_base_to_wifi_tf',
        # ),
        # Node(
        #     package='csi_ros',
        #     executable='world_to_base_tf',
        #     name='world_to_base_tf',
        # ),
        # Node(
        #     package='csi_ros',
        #     executable='world_to_home_tf',
        #     name='world_to_home_tf',
        # ),
    ])