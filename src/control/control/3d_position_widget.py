import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt, QTimer
import tf2_ros
import rclpy
import math

import geometry_msgs.msg

class Transform3DWidget(QWidget):
    def __init__(self, parent=None, target_frame='base_link', source_frame='home_frame'):
        super().__init__(parent)
        self.target_frame = target_frame
        self.source_frame = source_frame
        self.transform = None

        self.setMinimumSize(400, 400)
        self.label = QLabel("Waiting for transform...", self)
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        # ROS2 setup
        rclpy.init(args=None)
        self.node = rclpy.create_node('tf2_listener')
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self.node)

        # Timer to update transform
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_transform)
        self.timer.start(100)  # 10 Hz

    def update_transform(self):
        rclpy.spin_once(self.node, timeout_sec=0)
        try:
            trans = self.tf_buffer.lookup_transform(
                self.source_frame,
                self.target_frame,
                rclpy.time.Time())
            self.transform = trans.transform
            self.label.setText(f"Transform: {self.transform.translation.x:.2f}, "
                               f"{self.transform.translation.y:.2f}, "
                               f"{self.transform.translation.z:.2f}")
            self.update()
        except Exception as e:
            self.label.setText("Transform not available")

    def paintEvent(self, event):
        if not self.transform:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Draw axes
        painter.setPen(QColor(200, 200, 200))
        painter.drawLine(w//2, h//2, w//2, h//2-100)  # Z axis
        painter.drawLine(w//2, h//2, w//2+100, h//2)  # X axis
        painter.drawLine(w//2, h//2, w//2, h//2+100)  # -Z axis

        # Draw transform as a point
        x = self.transform.translation.x * 50 + w//2
        y = -self.transform.translation.y * 50 + h//2
        painter.setBrush(QColor(255, 0, 0))
        painter.drawEllipse(int(x)-5, int(y)-5, 10, 10)

        # Optionally draw orientation as an arrow
        q = self.transform.rotation
        yaw = math.atan2(2.0*(q.w*q.z + q.x*q.y), 1.0 - 2.0*(q.y*q.y + q.z*q.z))
        arrow_len = 30
        end_x = x + arrow_len * math.cos(yaw)
        end_y = y - arrow_len * math.sin(yaw)
        painter.setPen(QColor(0, 0, 255))
        painter.drawLine(int(x), int(y), int(end_x), int(end_y))

    def closeEvent(self, event):
        self.node.destroy_node()
        rclpy.shutdown()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = Transform3DWidget()
    widget.show()
    sys.exit(app.exec())