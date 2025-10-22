import matplotlib.pyplot as plt
import numpy as np

# Create a 3D boolean array representing occupied voxels
voxelarray = np.zeros((10, 10, 10), dtype=bool)
voxelarray[2:8, 2:8, 2:8] = True  # Create a cube of occupied voxels
voxelarray[0, 0, 0] = True
fig = plt.figure()
ax = fig.add_subplot(projection='3d')
ax.voxels(voxelarray, edgecolor='k') # 'k' for black edges

# Remove the axes, grids, and numbers
ax.axis('off')

plt.show()