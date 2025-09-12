import sys
import rclpy
import pyqtgraph as pg
import pyqtgraph.opengl as gl
import numpy as np
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from tf2_ros import TransformListener, Buffer
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, QObject
from geometry_msgs.msg import TransformStamped

# A QObject that emits a signal when a new transform is available.
class TfSignal(QObject):
    transform_ready = pyqtSignal(TransformStamped)

# A worker class for the ROS 2 node. It runs in a separate thread.
class RosTfWorker(QObject):
    def __init__(self, node_name='tf_listener_gui_node'):
        super().__init__()
        self.node = Node(node_name)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self.node)
        self.signal = TfSignal()
        self.timer = self.node.create_timer(0.01, self.timer_callback)
        self.source_frame = "world"
        self.target_frame = "base_link"

    def set_frames(self, source, target):
        self.source_frame = source
        self.target_frame = target
        self.node.get_logger().info(f"Listening for transform from {self.source_frame} to {self.target_frame}")

    def timer_callback(self):
        try:
            # Look up the transform at the latest available time
            transform = self.tf_buffer.lookup_transform(
                self.source_frame,
                self.target_frame,
                rclpy.time.Time())
            self.signal.transform_ready.emit(transform)
        except Exception as e:
            # Handle tf2 exceptions (e.g., frames not available yet)
            pass

    def spin(self):
        rclpy.spin(self.node)

    def shutdown(self):
        self.node.destroy_node()
        rclpy.shutdown()

class TFViewer(QMainWindow):
    def __init__(self, ros_worker):
        super().__init__()
        self.ros_worker = ros_worker
        self.setWindowTitle("ROS 2 TF2 Viewer")
        self.setGeometry(100, 100, 800, 600)

        # Set up the main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Pyqtgraph 3D view
        self.plot_widget = gl.GLViewWidget()
        layout.addWidget(self.plot_widget)
        self.plot_widget.setCameraPosition(distance=10)
        self.plot_widget.setWindowTitle("Real-time TF2 Visualization")

        # Add a grid for a ground plane
        grid = gl.GLGridItem()
        self.plot_widget.addItem(grid)

        # Add x,y,z axes
        axes = gl.GLAxisItem()
        self.plot_widget.addItem(axes)

        # Create a single GLScatterPlotItem to represent the transform
        # We will update its position and orientation in real-time
        self.tf_marker = gl.GLScatterPlotItem(
            pos=np.array([[0,0,0]], dtype=np.float32),
            size=[0.5],
            color=[[1, 0, 0, 1]],
            pxMode=False
        )
        self.plot_widget.addItem(self.tf_marker)

        # Label to display current pose data
        self.pose_label = QLabel("Waiting for TF data...")
        layout.addWidget(self.pose_label)

        # Connect the ROS worker's signal to a slot in this class
        self.ros_worker.signal.transform_ready.connect(self.update_plot)
    
    def update_plot(self, transform):
        """
        Updates the 3D plot with the latest transform data.
        """
        translation = transform.transform.translation
        rotation = transform.transform.rotation
        
        # Explicitly convert the list of coordinates to a NumPy array
        # This is the most likely fix for the drawing error
        new_pos = np.array([[translation.x, translation.y, translation.z]], dtype=np.float32)
        if np.all(np.isfinite(new_pos)):
            self.tf_marker.setData(pos=new_pos)
        
        # Update the label with the latest pose info
        label_text = (
            f"**Current Transform**\n"
            f"Translation (x, y, z): ({translation.x:.2f}, {translation.y:.2f}, {translation.z:.2f})\n"
            f"Rotation (qx, qy, qz, qw): ({rotation.x:.2f}, {rotation.y:.2f}, {rotation.z:.2f}, {rotation.w:.2f})"
        )
        self.pose_label.setText(label_text)

# Main application entry point
if __name__ == '__main__':
    # Initialize rclpy
    rclpy.init()

    # Create and start the ROS 2 node in a separate thread
    ros_thread = QThread()
    ros_worker = RosTfWorker()
    ros_worker.moveToThread(ros_thread)
    ros_thread.started.connect(ros_worker.spin)
    ros_thread.start()

    # Create and run the PyQt application
    app = QApplication(sys.argv)
    viewer = TFViewer(ros_worker)
    viewer.show()

    # Clean up on exit
    app.exec()
    ros_worker.shutdown()
    ros_thread.quit()
    ros_thread.wait()
