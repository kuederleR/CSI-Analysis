import open3d as o3d
import numpy as np

# Create a sample point cloud
pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(np.random.rand(100, 3))
pcd.colors = o3d.utility.Vector3dVector(np.random.rand(100, 3))

# Create a VoxelGrid from the point cloud
voxel_grid = o3d.geometry.VoxelGrid.create_from_point_cloud(pcd, voxel_size=0.1)

# Visualize the voxel grid
o3d.visualization.draw_geometries([voxel_grid])