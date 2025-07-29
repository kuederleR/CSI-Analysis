import rclpy
from rclpy.node import Node

class CSILogger(Node):
    def __init__(self):
        super().__init__('csi_logger')