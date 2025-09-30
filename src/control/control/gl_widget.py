import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, QFileDialog, QSplitter, QHBoxLayout
import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import QTimer, QObject, pyqtSignal, Qt
import time
import threading
from collections import deque

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from tf2_ros import Buffer, TransformListener
from geometry_msgs.msg import PoseStamped

from wifi_msgs.msg import CSI

import pyqtgraph.opengl as gl
from log_manager import LogManager

class PoseBridge(QObject):
    """
    Thread-safe bridge: emit pose updates from ROS thread, handled in GUI thread.
    """
    pose_received = pyqtSignal(object, object)  # position(list[3]), quaternion(list[4])
    def __init__(self):
        super().__init__()

class RosSpinThread(threading.Thread):
    """
    Spins a ROS executor without touching Qt. Allows graceful stop.
    """
    def __init__(self, *nodes):
        super().__init__(daemon=True)
        self._stop_evt = threading.Event()
        self.nodes = nodes

    def run(self):
        from rclpy.executors import SingleThreadedExecutor
        executor = SingleThreadedExecutor()
        for node in self.nodes:
            executor.add_node(node)
        try:
            while not self._stop_evt.is_set():
                executor.spin_once(timeout_sec=0.1)
        finally:
            for node in self.nodes:
                executor.remove_node(node)

    def stop(self):
        self._stop_evt.set()


class CSIBridge(QObject):
    """
    Thread-safe bridge for CSI data: emit updates from ROS thread, handled in GUI thread.
    """
    csi_received = pyqtSignal(object, object, int)  # (amplitude list, phase list, num_subcarriers)
    def __init__(self):
        super().__init__()


class CSIPlotWidget(QWidget):
    """Simple 2D plot for CSI amplitude/phase over subcarrier index."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        title = QLabel("CSI Graph (Amplitude vs Subcarrier)")
        title.setStyleSheet("color: #ddd; font-weight: bold; padding: 2px;")
        layout.addWidget(title)

        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel('bottom', 'Subcarrier Index')
        self.plot.setLabel('left', 'Amplitude')
        self.curve = self.plot.plot(pen=pg.mkPen((255, 255, 0), width=2))
        layout.addWidget(self.plot)

        # Secondary phase plot
        self.phase_plot = pg.PlotWidget()
        self.phase_plot.showGrid(x=True, y=True, alpha=0.3)
        self.phase_plot.setLabel('bottom', 'Subcarrier Index')
        self.phase_plot.setLabel('left', 'Phase (rad)')
        self.phase_curve = self.phase_plot.plot(pen=pg.mkPen((0, 200, 255), width=2))
        layout.addWidget(self.phase_plot)

        # Average amplitude over time plot
        self.avg_plot = pg.PlotWidget()
        self.avg_plot.showGrid(x=True, y=True, alpha=0.3)
        self.avg_plot.setLabel('bottom', 'Time (s)')
        self.avg_plot.setLabel('left', 'Avg Amplitude')
        self.avg_curve = self.avg_plot.plot(pen=pg.mkPen((0, 255, 100), width=2))
        layout.addWidget(self.avg_plot)

        self.setLayout(layout)

        # Keep last x vector to avoid reallocating each update when size matches
        self._last_n = 0
        self._x = np.array([], dtype=float)
        # Rolling buffer for average amplitude time series
        self._avg_t0 = None
        self._avg_times = deque(maxlen=2000)
        self._avg_values = deque(maxlen=2000)

    def update_data(self, amplitude_list, phase_list, num_subcarriers: int):
        # Convert to numpy arrays
        amps = np.asarray(amplitude_list, dtype=float)
        phs = np.asarray(phase_list, dtype=float)
        n = int(num_subcarriers) if num_subcarriers else len(amps)
        if n <= 0:
            return
        if amps.size < n:
            n = amps.size
        if phs.size < n:
            n = min(n, phs.size)
        if n != self._last_n:
            self._x = np.arange(n, dtype=float)
            self._last_n = n
        # slice in case arrays are longer
        self.curve.setData(self._x[:n], amps[:n])
        self.phase_curve.setData(self._x[:n], phs[:n])
        # Update average amplitude over time
        avg_val = float(np.mean(amps[:n])) if n > 0 else 0.0
        now = time.monotonic()
        if self._avg_t0 is None:
            self._avg_t0 = now
        t = now - self._avg_t0
        self._avg_times.append(t)
        self._avg_values.append(avg_val)
        # Convert to numpy for plotting
        if len(self._avg_times) > 1:
            t_arr = np.fromiter(self._avg_times, dtype=float)
            v_arr = np.fromiter(self._avg_values, dtype=float)
            self.avg_curve.setData(t_arr, v_arr)
            # Keep x-range auto; optionally clamp to last 60s by trimming deque size

class GLWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.gl_view = gl.GLViewWidget()

        layout.addWidget(self.gl_view)
        # Add scale label
        # self.scale_label = QLabel("Scale: 1 unit (axes length = 10)")
        # self.scale_label.setStyleSheet("color: #ccc; font-size: 11px; padding: 2px;")

        # layout.addWidget(self.scale_label)
        self.setLayout(layout)


        # Add axes and grid
        self._add_axes(length=10)
        self._add_grid(size=20, spacing=1)

        # Robot pose figure
        self.robot_pose = RobotPoseFigure(self.gl_view, axis_length=0.5)
        self.robot_pose.update_pose([0, 0, 0], [1, 0, 0, 0])  # identity orientation

        # Logging controls row
        self.log_manager_layout = QHBoxLayout()
        self.log_dir_label = QLabel("Log dir: (not set)")
        self.log_dir_label.setStyleSheet("color:#ccc; padding:2px;")
        self.choose_dir_btn = QPushButton("Choose Log Dir")
        self.start_log_btn = QPushButton("Start Log")
        self.stop_log_btn = QPushButton("Stop Log")
        self.stop_log_btn.setEnabled(False)
        self.log_manager_layout.addWidget(self.log_dir_label)
        self.log_manager_layout.addWidget(self.choose_dir_btn)
        self.log_manager_layout.addWidget(self.start_log_btn)
        self.log_manager_layout.addWidget(self.stop_log_btn)
        layout.addLayout(self.log_manager_layout)

        # Logging state
        self._log_dir = None
        self._log_mgr = None  # type: ignore[assignment]
        self.choose_dir_btn.clicked.connect(self._choose_log_dir)
        self.start_log_btn.clicked.connect(self._start_log)
        self.stop_log_btn.clicked.connect(self._stop_log)

        self.view_reset_btn = QPushButton("Reset View")
        self.view_reset_btn.setStyleSheet("font-size: 11px; padding: 2px;")
        self.view_reset_btn.clicked.connect(self._reset_view)
        layout.addWidget(self.view_reset_btn)

        self.trajectory_clear_btn = QPushButton("Clear Trajectory")
        self.trajectory_clear_btn.setStyleSheet("font-size: 11px; padding: 2px;")
        layout.addWidget(self.trajectory_clear_btn)
        self.trajectory_clear_btn.clicked.connect(self.robot_pose.clear_trajectory)

        self.export_btn = QPushButton("Export Scene")
        self.export_btn.setStyleSheet("font-size: 11px; padding: 2px;")
        self.export_btn.clicked.connect(self.export_scene)
        layout.addWidget(self.export_btn)

        self._reset_view()

    def get_robot_pose_figure(self):
        return self.robot_pose

    def _add_axes(self, length=10):
        # Create X (red), Y (green), Z (blue) axes
        origin = np.array([0, 0, 0])
        x = np.array([origin, [length, 0, 0]])
        y = np.array([origin, [0, length, 0]])
        z = np.array([origin, [0, 0, length]])
        self.x_axis = gl.GLLinePlotItem(pos=x, color=(1, 0, 0, 1), width=2, antialias=True)
        self.y_axis = gl.GLLinePlotItem(pos=y, color=(0, 1, 0, 1), width=2, antialias=True)
        self.z_axis = gl.GLLinePlotItem(pos=z, color=(0, 0, 1, 1), width=2, antialias=True)
        self.gl_view.addItem(self.x_axis)
        self.gl_view.addItem(self.y_axis)
        self.gl_view.addItem(self.z_axis)

    def _add_grid(self, size=20, spacing=1):
        self.grid = gl.GLGridItem()
        self.grid.setSize(size, size, size)
        self.grid.setSpacing(spacing, spacing, spacing)
        self.grid.setDepthValue(10)  # Render behind points
        self.gl_view.addItem(self.grid)

    def _reset_view(self):
        self.gl_view.setCameraPosition(distance=6, elevation=-20, azimuth=45)
        self.gl_view.opts['fov'] = -60  # Field of view

    # -------------------- Logging controls --------------------
    def _choose_log_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Choose log directory")
        if directory:
            self._log_dir = directory
            self.log_dir_label.setText(f"Log dir: {directory}")

    def _start_log(self):
        from datetime import datetime
        if self._log_mgr is not None:
            return
        # Default to CWD if not set
        base_dir = self._log_dir or "."
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"{base_dir}/csi_pose_{ts}.json"
        try:
            self._log_mgr = LogManager(path)
        except Exception as e:
            self.log_dir_label.setText(f"Log error: {e}")
            self._log_mgr = None
            return
        self.start_log_btn.setEnabled(False)
        self.stop_log_btn.setEnabled(True)

    def _stop_log(self):
        if self._log_mgr is not None:
            try:
                self._log_mgr.close()
            finally:
                self._log_mgr = None
        self.stop_log_btn.setEnabled(False)
        self.start_log_btn.setEnabled(True)

    def export_scene(self):
        """
        Export current scene:
        - *.png: screenshot
        - *.obj: trajectory polyline + robot pose axes
        """
        path, _ = QFileDialog.getSaveFileName(
            self, "Export 3D Scene", "scene.obj",
            "OBJ (*.obj);;PNG Screenshot (*.png)"
        )
        if not path:
            return
        if path.lower().endswith('.png'):
            img = self.gl_view.grabFramebuffer()
            img.save(path)
            return

        rp = self.robot_pose
        path_pts = list(rp._path_positions)
        axis_ends = getattr(rp, "_axis_endpoints", None)
        center = rp._last_pos if rp._last_pos is not None else np.array([0, 0, 0], float)

        with open(path, 'w') as f:
            f.write("# Exported 3D scene (trajectory + robot pose axes)\n")
            # Vertices: path first
            for p in path_pts:
                f.write(f"v {p[0]} {p[1]} {p[2]}\n")
            base_idx = len(path_pts)
            # Center
            f.write(f"v {center[0]} {center[1]} {center[2]}\n")
            # Axis endpoints
            if axis_ends is not None:
                for e in axis_ends:
                    f.write(f"v {e[0]} {e[1]} {e[2]}\n")
            # Polyline for path
            if len(path_pts) >= 2:
                indices = " ".join(str(i+1) for i in range(len(path_pts)))
                f.write(f"l {indices}\n")
            # Axis lines (center to each endpoint)
            if axis_ends is not None:
                c_idx = base_idx + 1
                for i in range(3):
                    f.write(f"l {c_idx} {c_idx + 1 + i}\n")

    # -------------------- Logging data handlers --------------------
    def handle_pose_for_logging(self, position, quaternion):
        if self._log_mgr is not None:
            try:
                self._log_mgr.update_pose(position, quaternion)
            except Exception:
                pass

    def handle_csi_for_logging(self, amplitude_list, phase_list, num_subcarriers):
        if self._log_mgr is not None:
            try:
                self._log_mgr.log_csi(amplitude_list, phase_list, num_subcarriers)
            except Exception:
                pass

class RobotPoseFigure:
    def __init__(self, gl_view, axis_length=1.0, center_color=(1, 1, 1, 1), center_size=5):
        self.view = gl_view
        self.axis_length = axis_length
        # Initialize axis line items
        zeros = np.array([[0, 0, 0], [0, 0, 0]], dtype=float)
        self.x_axis = gl.GLLinePlotItem(pos=zeros, color=(1, 0, 0, 1), width=3, antialias=True)
        self.y_axis = gl.GLLinePlotItem(pos=zeros, color=(0, 1, 0, 1), width=3, antialias=True)
        self.z_axis = gl.GLLinePlotItem(pos=zeros, color=(0, 0, 1, 1), width=3, antialias=True)
        self.center = gl.GLScatterPlotItem(pos=np.array([[0, 0, 0]]), color=center_color, size=center_size)
        # Path trail setup
        self._path_positions = deque(maxlen=2000)  # configurable length
        self._last_pos = None
        self._min_dist = 0.005  # threshold to append new point
        self.path_line = gl.GLLinePlotItem(pos=np.empty((0, 3)), color=(1, 1, 0, 0.7), width=2, antialias=True)
        for item in (self.x_axis, self.y_axis, self.z_axis, self.center, self.path_line):
            self.view.addItem(item)
        self._axis_endpoints = np.zeros((3, 3), dtype=float)  # store last axis endpoints

    def clear_trajectory(self):
        """
        Clear the recorded trajectory path.
        """
        self._path_positions.clear()
        self._last_pos = None
        self.path_line.setData(pos=np.empty((0, 3)))

    def update_pose(self, position, quaternion):
        pos = np.asarray(position, dtype=float).reshape(3)
        # Path update (before orientation axes so axes reflect current pose)
        if self._last_pos is None or np.linalg.norm(pos - self._last_pos) > self._min_dist:
            self._path_positions.append(pos.copy())
            self._last_pos = pos
            if len(self._path_positions) >= 2:
                self.path_line.setData(pos=np.array(self._path_positions))
        q = np.asarray(quaternion, dtype=float).reshape(4)
        # Normalize quaternion
        n = np.linalg.norm(q)
        if n == 0:
            q = np.array([1, 0, 0, 0], dtype=float)
        else:
            q = q / n
        w, x, y, z = q
        # Rotation matrix
        R = np.array([
            [1 - 2*(y*y + z*z),     2*(x*y - z*w),       2*(x*z + y*w)],
            [2*(x*y + z*w),         1 - 2*(x*x + z*z),   2*(y*z - x*w)],
            [2*(x*z - y*w),         2*(y*z + x*w),       1 - 2*(x*x + y*y)]
        ])
        axes = np.eye(3)  # unit X,Y,Z
        ends = (R @ axes.T).T * self.axis_length + pos
        self._axis_endpoints = ends  # store for export
        # Update line data
        self.x_axis.setData(pos=np.vstack([pos, ends[0]]))
        self.y_axis.setData(pos=np.vstack([pos, ends[1]]))
        self.z_axis.setData(pos=np.vstack([pos, ends[2]]))
        self.center.setData(pos=np.array([pos]))

    def link_node(self, node, bridge):
        """
        Connect a ROS node producing PoseStamped to this figure via a Qt signal bridge.
        """
        # Connect bridge signal to update_pose (runs in GUI thread)
        bridge.pose_received.connect(self.update_pose)
        node.set_pose_bridge(bridge)


class GUIPoseNode(Node):
    def __init__(self):
        super().__init__('gui_pose_node')
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.source_frame='world'
        self.target_frame='base_link'
        self._pose_bridge = None
        self.pose_sub = self.create_subscription(PoseStamped, '/qvio',
                                                 self.pose_callback, qos_profile_sensor_data)
        self.last_pose_time = None
        self.max_rate_hz = 20

    def set_pose_bridge(self, bridge: PoseBridge):
        self._pose_bridge = bridge

    def pose_callback(self, msg):
        translation = msg.pose.position
        rotation = msg.pose.orientation
        position = [translation.x, translation.y, translation.z]
        quaternion = [rotation.w, rotation.x, rotation.y, rotation.z]
        # Emit via bridge (thread-safe). GUI updates occur in main thread.
        if self._pose_bridge:
            self._pose_bridge.pose_received.emit(position, quaternion)

class GUICSIDataNode(Node):
    def __init__(self):
        super().__init__('gui_csi_data_node')
        self._bridge: CSIBridge | None = None
        self.csi_sub = self.create_subscription(CSI, '/csi_data', self.csi_callback, 10)

    def csi_callback(self, msg):
        # Forward data to GUI via bridge
        if self._bridge is not None:
            try:
                self._bridge.csi_received.emit(list(msg.csi_amplitude), list(msg.csi_phase), int(msg.num_subcarriers))
            except Exception:
                # Be robust to type issues
                amps = [float(x) for x in msg.csi_amplitude]
                phs = [float(x) for x in msg.csi_phase]
                nsc = int(getattr(msg, 'num_subcarriers', len(amps)))
                self._bridge.csi_received.emit(amps, phs, nsc)

    def set_bridge(self, bridge: CSIBridge):
        self._bridge = bridge
        

class VisWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pose + CSI Viewer")
        # Left: 3D Pose, Right: 2D CSI
        container = QWidget(self)
        hbox = QHBoxLayout(container)
        hbox.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, container)
        hbox.addWidget(self.splitter)
        container.setLayout(hbox)

        self.viewer = GLWidget(container)
        self.csi_plot = CSIPlotWidget(container)
        self.splitter.addWidget(self.viewer)
        self.splitter.addWidget(self.csi_plot)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        self.setCentralWidget(container)

        # Create ROS node & bridge
        self.pose_node = GUIPoseNode()
        self.pose_bridge = PoseBridge()
        self.viewer.robot_pose.link_node(self.pose_node, self.pose_bridge)
        # Also forward pose to logger via viewer (GUI thread)
        self.pose_bridge.pose_received.connect(self.viewer.handle_pose_for_logging)

        self.csi_node = GUICSIDataNode()
        self.csi_bridge = CSIBridge()
        self.csi_bridge.csi_received.connect(self.csi_plot.update_data)
        self.csi_node.set_bridge(self.csi_bridge)
        # Also forward CSI to logger via viewer (GUI thread)
        self.csi_bridge.csi_received.connect(self.viewer.handle_csi_for_logging)

        # Start ROS spin thread
        self.ros_thread = RosSpinThread(self.pose_node, self.csi_node)
        self.ros_thread.start()

    def closeEvent(self, event):
        # Graceful shutdown
        # Close logger if open
        try:
            if getattr(self.viewer, '_log_mgr', None) is not None:
                self.viewer._log_mgr.close()
        except Exception:
            pass
        if hasattr(self, 'ros_thread'):
            self.ros_thread.stop()
            self.ros_thread.join(timeout=1.0)
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass
        super().closeEvent(event)

if __name__ == "__main__":
    rclpy.init()
    app = QApplication(sys.argv)
    window = VisWindow()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())