import sys
from pathlib import Path
from typing import List, Tuple

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QLabel, QMessageBox, QHBoxLayout
)
from PyQt6.QtCore import Qt

import numpy as np
import pyqtgraph as pg  # noqa: F401  (pyqtgraph.opengl relies on base import side-effects)
import pyqtgraph.opengl as gl


class SimpleOBJ:
    """Minimal OBJ representation for files exported by `gl_widget.py`.

    Supported elements:
    - v x y z          (vertex positions)
    - l i j k ...      (polyline, 1-based vertex indices)
    Comments (# ...) are ignored.
    """
    def __init__(self):
        self.vertices: List[np.ndarray] = []  # list of (3,)
        # Each entry: numpy array shape (N, 3) representing a polyline in order
        self.polylines: List[np.ndarray] = []

    @staticmethod
    def parse(path: Path) -> 'SimpleOBJ':
        obj = SimpleOBJ()
        try:
            with path.open('r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split()
                    if parts[0] == 'v' and len(parts) >= 4:
                        try:
                            v = np.array(list(map(float, parts[1:4])), dtype=float)
                            obj.vertices.append(v)
                        except ValueError:
                            # Ignore malformed vertex line
                            continue
                    elif parts[0] == 'l' and len(parts) >= 3:
                        indices = []
                        ok = True
                        for p in parts[1:]:
                            try:
                                indices.append(int(p) - 1)  # convert 1-based to 0-based
                            except ValueError:
                                ok = False
                                break
                        if not ok or len(indices) < 2:
                            continue
                        # Build polyline points array
                        pts = []
                        for idx in indices:
                            if 0 <= idx < len(obj.vertices):
                                pts.append(obj.vertices[idx])
                        if len(pts) >= 2:
                            obj.polylines.append(np.vstack(pts))
        except OSError as e:
            raise RuntimeError(f"Failed to read OBJ file: {e}")
        return obj

    def bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        if not self.vertices:
            return np.zeros(3), np.zeros(3)
        allv = np.vstack(self.vertices)
        return allv.min(axis=0), allv.max(axis=0)


class OBJViewerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.view = gl.GLViewWidget()
        layout.addWidget(self.view)

        # Status label
        self.status_lbl = QLabel("No file loaded")
        self.status_lbl.setStyleSheet("color:#ccc; font-size:11px; padding:2px;")

        btn_row = QHBoxLayout()
        self.open_btn = QPushButton("Open OBJ")
        self.reset_btn = QPushButton("Reset View")
        btn_row.addWidget(self.open_btn)
        btn_row.addWidget(self.reset_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        layout.addWidget(self.status_lbl)

        self.setLayout(layout)

        self._grid = None
        self._axes_items = []
        self._poly_items: List[gl.GLLinePlotItem] = []

        self._install_scene_basics()
        self._connect()
        self.reset_camera()

    # ------------------------------------------------------------------
    def _install_scene_basics(self):
        # Grid
        grid = gl.GLGridItem()
        grid.setSize(20, 20, 20)
        grid.setSpacing(1, 1, 1)
        grid.setDepthValue(10)
        self.view.addItem(grid)
        self._grid = grid
        # Axes
        self._add_axes(length=2.0)

    def _add_axes(self, length=2.0):
        origin = np.array([0, 0, 0])
        x = np.array([origin, [length, 0, 0]])
        y = np.array([origin, [0, length, 0]])
        z = np.array([origin, [0, 0, length]])
        items = [
            gl.GLLinePlotItem(pos=x, color=(1, 0, 0, 1), width=2, antialias=True),
            gl.GLLinePlotItem(pos=y, color=(0, 1, 0, 1), width=2, antialias=True),
            gl.GLLinePlotItem(pos=z, color=(0, 0, 1, 1), width=2, antialias=True),
        ]
        for it in items:
            self.view.addItem(it)
        self._axes_items = items

    def _connect(self):
        self.open_btn.clicked.connect(self.open_file_dialog)
        self.reset_btn.clicked.connect(self.reset_camera)

    # ------------------------------------------------------------------
    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open OBJ File", str(Path.cwd()), "OBJ Files (*.obj)"
        )
        if not path:
            return
        self.load_obj(Path(path))

    def load_obj(self, path: Path):
        try:
            obj = SimpleOBJ.parse(path)
        except RuntimeError as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        # Clear existing polylines
        for item in self._poly_items:
            self.view.removeItem(item)
        self._poly_items.clear()

        # Add new polylines
        colors_cycle = [
            (1, 1, 0, 0.9),  # yellow (trajectory typical)
            (1, 0.5, 0, 0.9),
            (0, 1, 1, 0.9),
            (1, 0, 1, 0.9),
            (0.8, 0.8, 0.8, 0.9)
        ]
        for i, poly in enumerate(obj.polylines):
            color = colors_cycle[i % len(colors_cycle)]
            item = gl.GLLinePlotItem(pos=poly, color=color, width=2, antialias=True)
            self.view.addItem(item)
            self._poly_items.append(item)

        # Fit camera
        mn, mx = obj.bounds()
        center = (mn + mx) / 2.0
        extent = float(np.linalg.norm(mx - mn))
        if extent == 0:
            extent = 1.0
        # Move camera: distance heuristic
        self.view.setCameraPosition(pos=pg.Vector(center[0], center[1], center[2]), distance=extent * 1.5 + 2.0)

        self.status_lbl.setText(f"Loaded: {path.name} | Vertices: {len(obj.vertices)} | Polylines: {len(obj.polylines)}")

    def reset_camera(self):
        self.view.setCameraPosition(distance=10, elevation=-20, azimuth=45)
        self.view.opts['fov'] = -60


class OBJViewerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OBJ Scene Viewer")
        self.viewer = OBJViewerWidget(self)
        self.setCentralWidget(self.viewer)
        self.resize(900, 700)


def main():
    app = QApplication(sys.argv)
    win = OBJViewerWindow()
    win.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
