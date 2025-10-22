"""
Visualize the voxels intersected by a line segment between two points using matplotlib.
"""
import matplotlib.pyplot as plt
import numpy as np

# Define the spatial region of interest
REGION_MIN = (0, 0, 0)
REGION_MAX = (10, 10, 10)

# Define the two points
POINT_A = (1, 1, 3)
POINT_B = (8, 8, 8)

# Define the voxel size
VOXEL_SIZE = 1


def compute_voxel_intersect(point_a, point_b, region_min, region_max, voxel_size):
    """
    Compute the voxels intersected by the line segment from point_a to point_b
    within the defined region using a 3D DDA (Digital Differential Analyzer) algorithm.

    Args:
        point_a (tuple): The starting point (x, y, z).
        point_b (tuple): The ending point (x, y, z).
        region_min (tuple): The minimum corner of the region (x_min, y_min, z_min).
        region_max (tuple): The maximum corner of the region (x_max, y_max, z_max).
        voxel_size (float): The size of each voxel.

    Returns:
        list: A list of voxel coordinates (i, j, k) that are intersected by the line segment.
    """
    intersected_voxels = []
    
    x0, y0, z0 = point_a
    x1, y1, z1 = point_b
    
    # Calculate differences
    dx = x1 - x0
    dy = y1 - y0
    dz = z1 - z0
    
    # Determine the number of steps based on voxel size
    distance = np.sqrt(dx**2 + dy**2 + dz**2)
    steps = int(distance / voxel_size * 10)  # Oversample for better accuracy
    
    if steps == 0:
        # Same point - convert to voxel coordinates
        voxel_i = int(np.floor((x0 - region_min[0]) / voxel_size))
        voxel_j = int(np.floor((y0 - region_min[1]) / voxel_size))
        voxel_k = int(np.floor((z0 - region_min[2]) / voxel_size))
        
        # Calculate grid dimensions
        grid_i = int(np.ceil((region_max[0] - region_min[0]) / voxel_size))
        grid_j = int(np.ceil((region_max[1] - region_min[1]) / voxel_size))
        grid_k = int(np.ceil((region_max[2] - region_min[2]) / voxel_size))
        
        if (0 <= voxel_i < grid_i and
            0 <= voxel_j < grid_j and
            0 <= voxel_k < grid_k):
            return [(voxel_i, voxel_j, voxel_k)]
        return []
    
    # Calculate increments
    x_inc = dx / steps
    y_inc = dy / steps
    z_inc = dz / steps
    
    # Traverse the line
    x, y, z = x0, y0, z0
    voxel_set = set()
    
    # Calculate grid dimensions
    grid_i = int(np.ceil((region_max[0] - region_min[0]) / voxel_size))
    grid_j = int(np.ceil((region_max[1] - region_min[1]) / voxel_size))
    grid_k = int(np.ceil((region_max[2] - region_min[2]) / voxel_size))
    
    for _ in range(steps + 1):
        # Convert world coordinates to voxel grid indices
        voxel_i = int(np.floor((x - region_min[0]) / voxel_size))
        voxel_j = int(np.floor((y - region_min[1]) / voxel_size))
        voxel_k = int(np.floor((z - region_min[2]) / voxel_size))
        
        # Check if voxel is within bounds
        if (0 <= voxel_i < grid_i and
            0 <= voxel_j < grid_j and
            0 <= voxel_k < grid_k):
            voxel_set.add((voxel_i, voxel_j, voxel_k))
        
        x += x_inc
        y += y_inc
        z += z_inc
    
    return sorted(list(voxel_set))


def visualize_line_and_voxels(point_a, point_b, region_min, region_max, voxel_size):
    """
    Visualize the line segment and intersected voxels using matplotlib.
    
    Args:
        point_a (tuple): The starting point (x, y, z).
        point_b (tuple): The ending point (x, y, z).
        region_min (tuple): The minimum corner of the region (x_min, y_min, z_min).
        region_max (tuple): The maximum corner of the region (x_max, y_max, z_max).
        voxel_size (float): The size of each voxel.
    """
    # Compute intersected voxels
    intersected_voxels = compute_voxel_intersect(point_a, point_b, region_min, region_max, voxel_size)
    
    print(f"Line from {point_a} to {point_b}")
    print(f"Voxel size: {voxel_size}")
    print(f"Intersected {len(intersected_voxels)} voxels:")
    for voxel in intersected_voxels:
        # Convert voxel indices back to world coordinates for display
        world_x = region_min[0] + voxel[0] * voxel_size
        world_y = region_min[1] + voxel[1] * voxel_size
        world_z = region_min[2] + voxel[2] * voxel_size
        print(f"  Voxel {voxel} -> World coords: ({world_x:.2f}, {world_y:.2f}, {world_z:.2f})")
    
    # Create a 3D boolean array for the voxel grid
    grid_i = int(np.ceil((region_max[0] - region_min[0]) / voxel_size))
    grid_j = int(np.ceil((region_max[1] - region_min[1]) / voxel_size))
    grid_k = int(np.ceil((region_max[2] - region_min[2]) / voxel_size))
    grid_size = (grid_i, grid_j, grid_k)
    voxelarray = np.zeros(grid_size, dtype=bool)
    
    # Mark intersected voxels
    for voxel in intersected_voxels:
        voxelarray[voxel] = True
    
    # Create the figure and 3D axis
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(projection='3d')
    
    # Create filled voxels with proper positioning
    colors = np.zeros(voxelarray.shape + (4,))
    colors[voxelarray] = [0.2, 0.6, 1.0, 0.7]  # Blue with transparency
    
    # Create a coordinate mesh that accounts for voxel_size
    # matplotlib's voxels() function treats each voxel as having size 1
    # We need to scale and shift to match our actual voxel size
    x = np.arange(0, grid_i + 1) * voxel_size + region_min[0]
    y = np.arange(0, grid_j + 1) * voxel_size + region_min[1]
    z = np.arange(0, grid_k + 1) * voxel_size + region_min[2]
    
    # Plot each voxel manually to respect voxel_size
    for voxel in intersected_voxels:
        i, j, k = voxel
        x_pos = region_min[0] + i * voxel_size
        y_pos = region_min[1] + j * voxel_size
        z_pos = region_min[2] + k * voxel_size
        
        # Create vertices for a cube
        vertices = np.array([
            [x_pos, y_pos, z_pos],
            [x_pos + voxel_size, y_pos, z_pos],
            [x_pos + voxel_size, y_pos + voxel_size, z_pos],
            [x_pos, y_pos + voxel_size, z_pos],
            [x_pos, y_pos, z_pos + voxel_size],
            [x_pos + voxel_size, y_pos, z_pos + voxel_size],
            [x_pos + voxel_size, y_pos + voxel_size, z_pos + voxel_size],
            [x_pos, y_pos + voxel_size, z_pos + voxel_size]
        ])
        
        # Plot the cube edges
        edges = [
            [0, 1], [1, 2], [2, 3], [3, 0],  # bottom
            [4, 5], [5, 6], [6, 7], [7, 4],  # top
            [0, 4], [1, 5], [2, 6], [3, 7]   # sides
        ]
        for edge in edges:
            points = vertices[edge]
            ax.plot3D(*points.T, 'k-', linewidth=0.5)
        
        # Fill the voxel faces
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        faces = [
            [vertices[0], vertices[1], vertices[2], vertices[3]],  # bottom
            [vertices[4], vertices[5], vertices[6], vertices[7]],  # top
            [vertices[0], vertices[1], vertices[5], vertices[4]],  # front
            [vertices[2], vertices[3], vertices[7], vertices[6]],  # back
            [vertices[0], vertices[3], vertices[7], vertices[4]],  # left
            [vertices[1], vertices[2], vertices[6], vertices[5]]   # right
        ]
        poly = Poly3DCollection(faces, alpha=0.7, facecolor=[0.2, 0.6, 1.0], edgecolor='none')
        ax.add_collection3d(poly)
    
    # Plot the line segment
    line_x = [point_a[0], point_b[0]]
    line_y = [point_a[1], point_b[1]]
    line_z = [point_a[2], point_b[2]]
    ax.plot(line_x, line_y, line_z, 'r-', linewidth=3, label='Line segment')
    
    # Plot the points
    ax.scatter(*point_a, color='green', s=100, label=f'Point A {point_a}')
    ax.scatter(*point_b, color='red', s=100, label=f'Point B {point_b}')
    
    # Set labels and title
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_title('Voxels Intersected by Line Segment')
    ax.legend()
    
    # Set the viewing angle
    ax.view_init(elev=20, azim=45)
    
    # Set axis limits
    ax.set_xlim(region_min[0], region_max[0])
    ax.set_ylim(region_min[1], region_max[1])
    ax.set_zlim(region_min[2], region_max[2])
    
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    visualize_line_and_voxels(POINT_A, POINT_B, REGION_MIN, REGION_MAX, VOXEL_SIZE)
