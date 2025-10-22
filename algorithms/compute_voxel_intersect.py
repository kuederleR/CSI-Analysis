"""
A basic script for calculating the voxel intersections given two points.
"""

# Define the spatial region of interest
REGION_MIN = (0, 0, 0)
REGION_MAX = (10, 10, 10)

# Define the two points
POINT_A = (1, 1, 1)
POINT_B = (5, 5, 5)

# Define the voxel size
VOXEL_SIZE = 1.0

def compute_voxel_intersect(point_a, point_b, region_min, region_max):
    """
    Compute the voxels intersected by the line segment from point_a to point_b
    within the defined region.

    Args:
        point_a (tuple): The starting point (x, y, z).
        point_b (tuple): The ending point (x, y, z).
        region_min (tuple): The minimum corner of the region (x_min, y_min, z_min).
        region_max (tuple): The maximum corner of the region (x_max, y_max, z_max).

    Returns:
        list: A list of voxel coordinates (x, y, z) that are intersected by the line segment.
    """
    # Initialize the list of intersected voxels
    intersected_voxels = []

    # Compute the voxel coordinates for the line segment
    x0, y0, z0 = point_a
    x1, y1, z1 = point_b

    # Clip the line segment to the region boundaries
    x0 = max(region_min[0], min(region_max[0], x0))
    y0 = max(region_min[1], min(region_max[1], y0))
    z0 = max(region_min[2], min(region_max[2], z0))
    x1 = max(region_min[0], min(region_max[0], x1))
    y1 = max(region_min[1], min(region_max[1], y1))
    z1 = max(region_min[2], min(region_max[2], z1))

    # Compute the voxel coordinates for the line segment
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                intersected_voxels.append((x, y, z))

    return intersected_voxels

if __name__ == "__main__":
    intersected_voxels = compute_voxel_intersect(POINT_A, POINT_B, REGION_MIN, REGION_MAX)
    print("Intersected Voxels:")
    for voxel in intersected_voxels:
        print(voxel)