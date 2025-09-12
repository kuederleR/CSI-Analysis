import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import QTimer
import tf2_ros
import rclpy
import math
from transforms3d.euler import quat2euler
import geometry_msgs.msg
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class Transform3DWidget(QWidget):
    def __init__(self, parent=None, target_frame='base_link', source_frame='home_frame', ros_node=None):
        super().__init__(parent)
        self.target_frame = target_frame
        self.source_frame = source_frame
        self.transform = None
    # Breadcrumbs removed

        self.label = QLabel("Waiting for transform...", self)
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        # Matplotlib 3D Figure
        self.fig = Figure(figsize=(5, 4))
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.ax.set_xlim(-100, 100)
        self.ax.set_ylim(-100, 100)
        self.ax.set_zlim(-100, 100)
        self.ax.set_xlabel('X')
        self.ax.set_ylabel('Y')
        self.ax.set_zlabel('Z')

        self.node = ros_node
        self.tf_buffer = tf2_ros.Buffer()
        if self.node is not None:
            self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self.node)
        else:
            self.tf_listener = None

        self.timer = None

    def spin_once(self):
        """Spin once for ROS events and update transform."""
        self.update_transform()

    # Breadcrumbs feature removed

    # Breadcrumbs feature removed

    def begin(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_transform)
        self.timer.start(100)

    def update_transform(self):
        rclpy.spin_once(self.node, timeout_sec=0)
        try:
            trans = self.tf_buffer.lookup_transform(
                self.source_frame,
                self.target_frame,
                rclpy.time.Time())
            self.transform = trans.transform
            self.label.setText("")
            self.update_scene()
        except Exception:
            self.label.setText("Transform not available")

    def update_scene(self):
        self.ax.cla()
        self.ax.set_xlim(-100, 100)
        self.ax.set_ylim(-100, 100)
        self.ax.set_zlim(-100, 100)
        self.ax.set_xlabel('X')
        self.ax.set_ylabel('Y')
        self.ax.set_zlabel('Z')

        # Draw current transform and orientation
        if self.transform:
            x = self.transform.translation.x * 50
            y = self.transform.translation.y * 50
            z = self.transform.translation.z * 50
            self.ax.scatter([x], [y], [z], c='r', s=100, label='Current')

            # Orientation arrow
            q = self.transform.rotation
            quat = [q.w, q.x, q.y, q.z]
            # Convert quaternion to euler angles
            roll, pitch, yaw = quat2euler(quat, axes='sxyz')
            # Arrow direction (forward vector)
            dx = math.cos(yaw) * math.cos(pitch)
            dy = math.sin(yaw) * math.cos(pitch)
            dz = math.sin(pitch)
            self.ax.quiver(x, y, z, dx, dy, dz, length=20, color='b', label='Orientation')
        self.ax.legend()
        self.canvas.draw()

    def closeEvent(self, event):
        self.node.destroy_node()
        rclpy.shutdown()
        event.accept()

if __name__ == "__main__":
    rclpy.init()
    app = QApplication(sys.argv)
    widget = Transform3DWidget()
    widget.begin()
    widget.show()
    sys.exit(app.exec())
