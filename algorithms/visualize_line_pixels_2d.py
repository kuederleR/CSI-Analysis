"""
Visualize the pixels intersected by a line segment between two points in 2D using matplotlib.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

# Define the spatial region of interest
REGION_MIN = (0, 0)
REGION_MAX = (10, 10)

# Define the two points
POINT_A = (1, 3)
POINT_B = (8, 8)

# Define the pixel size
PIXEL_SIZE = 0.2


def compute_pixel_intersect(point_a, point_b, region_min, region_max, pixel_size):
    """
    Compute the pixels intersected by the line segment from point_a to point_b
    within the defined region using a 2D DDA (Digital Differential Analyzer) algorithm.

    Args:
        point_a (tuple): The starting point (x, y).
        point_b (tuple): The ending point (x, y).
        region_min (tuple): The minimum corner of the region (x_min, y_min).
        region_max (tuple): The maximum corner of the region (x_max, y_max).
        pixel_size (float): The size of each pixel.

    Returns:
        list: A list of pixel coordinates (i, j) that are intersected by the line segment.
    """
    intersected_pixels = []
    
    x0, y0 = point_a
    x1, y1 = point_b
    
    # Calculate differences
    dx = x1 - x0
    dy = y1 - y0
    
    # Determine the number of steps based on pixel size
    distance = np.sqrt(dx**2 + dy**2)
    steps = int(distance / pixel_size * 10)  # Oversample for better accuracy
    
    if steps == 0:
        # Same point - convert to pixel coordinates
        pixel_i = int(np.floor((x0 - region_min[0]) / pixel_size))
        pixel_j = int(np.floor((y0 - region_min[1]) / pixel_size))
        
        # Calculate grid dimensions
        grid_i = int(np.ceil((region_max[0] - region_min[0]) / pixel_size))
        grid_j = int(np.ceil((region_max[1] - region_min[1]) / pixel_size))
        
        if (0 <= pixel_i < grid_i and
            0 <= pixel_j < grid_j):
            return [(pixel_i, pixel_j)]
        return []
    
    # Calculate increments
    x_inc = dx / steps
    y_inc = dy / steps
    
    # Traverse the line
    x, y = x0, y0
    pixel_set = set()
    
    # Calculate grid dimensions
    grid_i = int(np.ceil((region_max[0] - region_min[0]) / pixel_size))
    grid_j = int(np.ceil((region_max[1] - region_min[1]) / pixel_size))
    
    for _ in range(steps + 1):
        # Convert world coordinates to pixel grid indices
        pixel_i = int(np.floor((x - region_min[0]) / pixel_size))
        pixel_j = int(np.floor((y - region_min[1]) / pixel_size))
        
        # Check if pixel is within bounds
        if (0 <= pixel_i < grid_i and
            0 <= pixel_j < grid_j):
            pixel_set.add((pixel_i, pixel_j))
        
        x += x_inc
        y += y_inc
    
    return sorted(list(pixel_set))


def visualize_line_and_pixels(point_a, point_b, region_min, region_max, pixel_size):
    """
    Visualize the line segment and intersected pixels using matplotlib.
    
    Args:
        point_a (tuple): The starting point (x, y).
        point_b (tuple): The ending point (x, y).
        region_min (tuple): The minimum corner of the region (x_min, y_min).
        region_max (tuple): The maximum corner of the region (x_max, y_max).
        pixel_size (float): The size of each pixel.
    """
    # Compute intersected pixels
    intersected_pixels = compute_pixel_intersect(point_a, point_b, region_min, region_max, pixel_size)
    
    print(f"Line from {point_a} to {point_b}")
    print(f"Pixel size: {pixel_size}")
    print(f"Intersected {len(intersected_pixels)} pixels:")
    for pixel in intersected_pixels:
        # Convert pixel indices back to world coordinates for display
        world_x = region_min[0] + pixel[0] * pixel_size
        world_y = region_min[1] + pixel[1] * pixel_size
        print(f"  Pixel {pixel} -> World coords: ({world_x:.2f}, {world_y:.2f})")
    
    # Create the figure and 2D axis
    fig, ax = plt.subplots(figsize=(10, 10))
    
    # Calculate grid dimensions
    grid_i = int(np.ceil((region_max[0] - region_min[0]) / pixel_size))
    grid_j = int(np.ceil((region_max[1] - region_min[1]) / pixel_size))
    
    # Draw grid lines
    for i in range(grid_i + 1):
        x = region_min[0] + i * pixel_size
        ax.plot([x, x], [region_min[1], region_max[1]], 'lightgray', linewidth=0.5, alpha=0.5)
    
    for j in range(grid_j + 1):
        y = region_min[1] + j * pixel_size
        ax.plot([region_min[0], region_max[0]], [y, y], 'lightgray', linewidth=0.5, alpha=0.5)
    
    # Plot each intersected pixel as a filled rectangle
    for pixel in intersected_pixels:
        i, j = pixel
        x_pos = region_min[0] + i * pixel_size
        y_pos = region_min[1] + j * pixel_size
        
        # Create a rectangle for the pixel
        rect = patches.Rectangle(
            (x_pos, y_pos), 
            pixel_size, 
            pixel_size,
            linewidth=1,
            edgecolor='black',
            facecolor='cornflowerblue',
            alpha=0.7
        )
        ax.add_patch(rect)
    
    # Plot the line segment
    line_x = [point_a[0], point_b[0]]
    line_y = [point_a[1], point_b[1]]
    ax.plot(line_x, line_y, 'r-', linewidth=3, label='Line segment', zorder=10)
    
    # Plot the points
    ax.scatter(*point_a, color='green', s=200, label=f'Point A {point_a}', zorder=11, edgecolors='black', linewidth=2)
    ax.scatter(*point_b, color='red', s=200, label=f'Point B {point_b}', zorder=11, edgecolors='black', linewidth=2)
    
    # Set labels and title
    ax.set_xlabel('X', fontsize=12)
    ax.set_ylabel('Y', fontsize=12)
    ax.set_title('Pixels Intersected by Line Segment (2D)', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    
    # Set axis limits and aspect ratio
    ax.set_xlim(region_min[0], region_max[0])
    ax.set_ylim(region_min[1], region_max[1])
    ax.set_aspect('equal')
    
    # Add grid
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    visualize_line_and_pixels(POINT_A, POINT_B, REGION_MIN, REGION_MAX, PIXEL_SIZE)
