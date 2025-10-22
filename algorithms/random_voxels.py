import open3d as o3d
import numpy as np
import threading
import time
import random
import os

# Set environment variables to help with Wayland/EGL issues
os.environ['DISPLAY'] = ':0'

class RandomVoxelGrid:
    def __init__(self, size=10, voxel_size=1.0):
        self.size = size
        self.voxel_size = voxel_size
        self.vis = o3d.visualization.Visualizer()
        # Try to create window without OpenGL errors
        try:
            self.vis.create_window(window_name="Random Voxel Grid", visible=True)
        except Exception as e:
            print(f"Warning: Could not create visible window: {e}")
            print("Trying alternative rendering...")
        self.voxel_grid = o3d.geometry.VoxelGrid()
        self.red_voxels = set()
        self.geometries = []
        self._init_grid()
        self.running = False

    def _init_grid(self):
        # Create an empty voxel grid
        self.voxel_grid = o3d.geometry.VoxelGrid.create_dense(
            origin=np.array([0.0, 0.0, 0.0]),
            color=np.array([0.5, 0.5, 0.5]),
            voxel_size=self.voxel_size,
            width=self.size * self.voxel_size,
            height=self.size * self.voxel_size,
            depth=self.size * self.voxel_size
        )
        self.vis.add_geometry(self.voxel_grid)

    def add_random_red_voxel(self):
        # Pick a random voxel coordinate
        while True:
            x = random.randint(0, self.size - 1)
            y = random.randint(0, self.size - 1)
            z = random.randint(0, self.size - 1)
            idx = (x, y, z)
            if idx not in self.red_voxels:
                self.red_voxels.add(idx)
                break
        # Create a small red cube at the voxel location
        cube = o3d.geometry.TriangleMesh.create_box(width=self.voxel_size, height=self.voxel_size, depth=self.voxel_size)
        cube.paint_uniform_color([1, 0, 0])
        cube.translate([x * self.voxel_size, y * self.voxel_size, z * self.voxel_size])
        self.geometries.append(cube)
        self.vis.add_geometry(cube, reset_bounding_box=False)
        self.vis.poll_events()
        self.vis.update_renderer()
        return True

    def run_random_voxel_adder(self):
        self.running = True
        def loop():
            while self.running:
                self.add_random_red_voxel()
                time.sleep(1)
        t = threading.Thread(target=loop)
        t.daemon = True
        t.start()

    def show(self):
        self.run_random_voxel_adder()
        try:
            while True:
                if not self.vis.poll_events():
                    break
                self.vis.update_renderer()
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("\nStopping visualization...")
        finally:
            self.running = False
            self.vis.destroy_window()

if __name__ == "__main__":
    grid_size = 10  # Change this to specify the grid size
    voxel_size = 1.0
    grid = RandomVoxelGrid(size=grid_size, voxel_size=voxel_size)
    grid.show()