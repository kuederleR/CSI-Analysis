import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QHBoxLayout
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
from wifi_msgs.msg import CSI

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from position_widget import Transform3DWidget

class StarlingControlWidget(QWidget):
    def __init__(self, ros_node):
        super().__init__()
        self.ros_node = ros_node
        self.ros_node.set_widget(self)
        self.rssi_values = []
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Starling Control')
        layout = QVBoxLayout()
        controls_widget = QWidget()
        controls_layout = QHBoxLayout()


        self.home_button = QPushButton('Home')
        self.home_button.clicked.connect(self.publish_home)
        controls_layout.addWidget(self.home_button)

        self.launch_button = QPushButton('Launch')
        controls_layout.addWidget(self.launch_button)

        controls_widget.setLayout(controls_layout)

        layout.addWidget(controls_widget)

        # Matplotlib Figure
        self.figure = Figure(figsize=(5, 3))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title('RSSI Over Time')
        self.ax.set_xlabel('Sample')
        self.ax.set_ylabel('RSSI')

        self.tw = Transform3DWidget(ros_node=self.ros_node)
        self.ros_node.set_spin_objects([self.tw])
        layout.addWidget(self.tw)

        self.setLayout(layout)

    def publish_home(self):
        msg = Bool(data=True)
        self.ros_node.publisher_home.publish(msg)

    def publish_topic1(self):
        msg = String()
        msg.data = 'Button 1 Pressed'
        self.ros_node.publisher1.publish(msg)

    def publish_topic2(self):
        msg = String()
        msg.data = 'Button 2 Pressed'
        self.ros_node.publisher2.publish(msg)

    def update_rssi(self, rssi):
        mapped_rssi = (rssi + 40) / 20 * 2 - 1  # Maps -40..-20 to -1..1
        self.tw.add_point(mapped_rssi)
        self.rssi_values.append(rssi)
        if len(self.rssi_values) > 100:
            self.rssi_values.pop(0)
        self.ax.clear()
        self.ax.plot(self.rssi_values)
        self.ax.set_title('RSSI Over Time')
        self.ax.set_xlabel('Sample')
        self.ax.set_ylabel('RSSI')
        self.canvas.draw()

class ControlNode(Node):
    def __init__(self, spin_objs = []):
        super().__init__('starling_control_node')
        self.publisher1 = self.create_publisher(String, 'topic1', 10)
        self.publisher2 = self.create_publisher(String, 'topic2', 10)

        self.csi_subscriber = self.create_subscription(
            CSI,
            'csi_data',
            self.csi_callback,
            10
        )
        self.publisher_home = self.create_publisher(Bool, 'set_starling_home', 10)
        self.spin_objects = spin_objs
        self.get_logger().info('Starling Control Node has been started.')

    def set_widget(self, widget):
        self.widget = widget

    def csi_callback(self, msg):
        # Spin 3D widget(s) to update transform
        for obj in self.spin_objects:
            if hasattr(obj, 'spin_once'):
                obj.spin_once()
        rssi = msg.rssi
        try:
            self.widget.update_rssi(rssi)
        except Exception:
            pass

    def set_spin_objects(self, spin_objects):
        self.spin_objects = spin_objects

def main():
    rclpy.init()
    ros_node = ControlNode()

    app = QApplication(sys.argv)
    widget = StarlingControlWidget(ros_node)
    widget.show()

    import threading
    ros_thread = threading.Thread(target=rclpy.spin, args=(ros_node,), daemon=True)
    ros_thread.start()

    app.exec()
    ros_node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()