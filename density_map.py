import numpy as np
import matplotlib.pyplot as plt
import sys
import argparse
from csi_py.csireader import CSIReader 
from scipy.signal import find_peaks, windows, medfilt 
from collections import deque 

# --- Configuration Parameters ---
WIFI_BANDWIDTH_HZ = 40e6 # 40 MHz Wi-Fi bandwidth
NUM_RAW_SUBCARRIERS = 56 
IFFT_POINTS = 128 

# Max Time of Flight to display on the X-axis (in nanoseconds).
# This sets the visible range for the Time of Flight.
# 200ns = 60m. For indoor environments, 50-100ns might be more relevant.
MAX_TOF_NS = 100 # Adjusted for typical indoor ranges (approx 30 meters)

# Filtering parameters
IFFT_WINDOW_TYPE = 'hamming' 
CSI_PACKET_AVG_COUNT = 5 # Average 5 packets for noise reduction

# Moving average window size for smoothing the CIR magnitude.
CIR_SMOOTHING_WINDOW_SIZE = 7 

# Median filter kernel size for CIR magnitude. Must be odd.
CIR_MEDIAN_FILTER_KERNEL = 3 

# --- SAR Visualization Parameters ---
MAX_SAR_FRAMES = 150 # Increased max frames for a longer synthetic aperture

# --- Global Plotting Variables ---
sar_plot_fig = None
sar_plot_ax = None
sar_plot_image = None
accumulated_cir_magnitudes = deque(maxlen=MAX_SAR_FRAMES) 
current_frame_line = None # To highlight the current frame

# Pre-calculate time axis for plotting, as it's constant
time_step_s_global = 1.0 / WIFI_BANDWIDTH_HZ 
time_axis_ns_global = np.arange(IFFT_POINTS) * time_step_s_global * 1e9

# Helper function for moving average
def moving_average_1d(data, window_size):
    """Applies a moving average filter to a 1D array."""
    if len(data) < window_size:
        window = len(data)
    else:
        window = window_size
    return np.convolve(data, np.ones(window)/window, mode='same')

def process_and_accumulate_cir_for_sar(raw_data_array):
    """
    Callback function to process raw CSI data into CIR, apply filters,
    and accumulate it for SAR-like visualization.
    Includes CSI packet averaging for noise reduction.

    Args:
        raw_data_array (list): A 1D Python list where elements alternate between
                                     real and imaginary components (112 elements for 56 subcarriers).
    """
    global sar_plot_fig, sar_plot_ax, sar_plot_image, accumulated_cir_magnitudes, current_frame_line

    if raw_data_array is None or len(raw_data_array) == 0:
        return

    # --- 1. Parse Raw Data to Complex CSI ---
    try:
        raw_data_np = np.array(raw_data_array) 
        reshaped_data = raw_data_np.reshape(-1, 2)
        complex_csi_current_packet = reshaped_data[:, 0] + 1j * reshaped_data[:, 1]
    except ValueError as e:
        print(f"Error reshaping raw data array: {e}. Expected 112 elements for 56 subcarriers. Raw data length: {len(raw_data_array)}")
        return
    
    num_subcarriers = len(complex_csi_current_packet)
    if num_subcarriers != NUM_RAW_SUBCARRIERS:
        print(f"Warning: Expected {NUM_RAW_SUBCARRIERS} subcarriers, but got {num_subcarriers}. Check input data format.")
    
    # --- Accumulate CSI packets for averaging ---
    # Need to handle the csi_buffer global (or make it a non-global, but passed around)
    # For simplicity, we'll keep it global for this callback context.
    # Note: `deque` needs to be initialized here if not global or passed explicitly
    # For consistency with previous code, let's assume it's global and managed.
    global csi_buffer
    if 'csi_buffer' not in globals():
        csi_buffer = deque(maxlen=CSI_PACKET_AVG_COUNT)
    
    csi_buffer.append(complex_csi_current_packet)

    if len(csi_buffer) < CSI_PACKET_AVG_COUNT:
        return
    
    averaged_complex_csi = np.mean(np.array(csi_buffer), axis=0)

    # --- 2. CSI Pre-processing (on averaged CSI) ---
    amplitudes = np.abs(averaged_complex_csi)
    phases = np.angle(averaged_complex_csi)
    subcarrier_indices = np.arange(num_subcarriers) 

    # Phase Correction/Sanitization
    if num_subcarriers == 0: 
        return

    corrected_phases_step1 = phases - phases[0]
    
    if len(subcarrier_indices) < 2:
        unwrapped_phases = phases 
    else:
        p_sfo = np.polyfit(subcarrier_indices, corrected_phases_step1, 1)
        sfo_correction = p_sfo[0] * subcarrier_indices + p_sfo[1]
        corrected_phases_step2 = corrected_phases_step1 - sfo_correction
        unwrapped_phases = np.unwrap(corrected_phases_step2) 
    
    cleaned_csi = amplitudes * np.exp(1j * unwrapped_phases)

    # --- Apply Windowing to CSI before IFFT ---
    if IFFT_WINDOW_TYPE == 'hamming':
        window = windows.hamming(num_subcarriers)
    elif IFFT_WINDOW_TYPE == 'hanning':
        window = windows.hanning(num_subcarriers)
    else: 
        window = np.ones(num_subcarriers)
    
    windowed_csi = cleaned_csi * window

    # --- 3. IFFT to get CIR ---
    fft_input = np.zeros(IFFT_POINTS, dtype=complex)
    
    if num_subcarriers > 1: 
        pos_freq_csi = windowed_csi[num_subcarriers // 2:] 
        neg_freq_csi = windowed_csi[0:num_subcarriers // 2] 
        fft_input[0 : len(pos_freq_csi)] = pos_freq_csi
        fft_input[IFFT_POINTS - len(neg_freq_csi) : IFFT_POINTS] = neg_freq_csi
    else: 
        fft_input[0] = windowed_csi[0] if num_subcarriers > 0 else 0
    
    cir = np.fft.ifft(fft_input)
    cir_magnitude = np.abs(cir)

    # --- Apply Smoothing to CIR Magnitude (Moving Average) ---
    if CIR_SMOOTHING_WINDOW_SIZE > 1 and len(cir_magnitude) > 1:
        cir_magnitude = moving_average_1d(cir_magnitude, CIR_SMOOTHING_WINDOW_SIZE)

    # --- Apply Median Filtering to CIR Magnitude ---
    if CIR_MEDIAN_FILTER_KERNEL is not None and CIR_MEDIAN_FILTER_KERNEL > 1 and CIR_MEDIAN_FILTER_KERNEL % 2 == 1:
        if len(cir_magnitude) >= CIR_MEDIAN_FILTER_KERNEL: 
            cir_magnitude = medfilt(cir_magnitude, kernel_size=CIR_MEDIAN_FILTER_KERNEL)
        else:
            print(f"Warning: CIR data ({len(cir_magnitude)} points) too short for median filter kernel ({CIR_MEDIAN_FILTER_KERNEL}). Skipping median filter.")


    # --- Accumulate CIR Magnitude for SAR Visualization ---
    if len(cir_magnitude) != IFFT_POINTS:
        print(f"CIR magnitude length mismatch: Expected {IFFT_POINTS}, got {len(cir_magnitude)}. Skipping SAR update.")
        return
        
    accumulated_cir_magnitudes.append(cir_magnitude)
    
    # --- 4. Plotting the SAR-like Image ---
    current_frame_index = len(accumulated_cir_magnitudes) -1 # 0-indexed
    
    if sar_plot_fig is None:
        plt.ion() 
        sar_plot_fig, sar_plot_ax = plt.subplots(figsize=(12, 7))
        
        dummy_data = np.zeros((MAX_SAR_FRAMES, IFFT_POINTS)) # Initialize with max size
        sar_plot_image = sar_plot_ax.imshow(
            dummy_data, 
            aspect='auto', 
            cmap='viridis', 
            origin='lower', # Puts first frame at bottom, last at top
            # extent: [xmin, xmax, ymin, ymax]
            extent=[time_axis_ns_global[0], MAX_TOF_NS, 0, MAX_SAR_FRAMES] 
        )
        
        # Add a vertical line at ToF = 0
        sar_plot_ax.axvline(0, color='red', linestyle='--', linewidth=1.5, label='ToF = 0 ns')
        
        # Initialize the current frame line outside the image extent to hide it initially
        current_frame_line, = sar_plot_ax.plot([0, MAX_TOF_NS], [-1, -1], color='cyan', linestyle='-', linewidth=2, label='Current Frame')

        sar_plot_ax.set_title(f"Basic RF Echo Map (CIR Magnitude) - {WIFI_BANDWIDTH_HZ/1e6:.0f} MHz Bandwidth", fontsize=14)
        sar_plot_ax.set_xlabel("Time of Flight (ns) - Distance from Sensor (1ns ≈ 0.3m)", fontsize=12)
        sar_plot_ax.set_ylabel("Drone Position / Scan Line Index", fontsize=12)
        sar_plot_ax.set_xlim(0, MAX_TOF_NS) 
        sar_plot_fig.colorbar(sar_plot_image, ax=sar_plot_ax, label='Echo Strength (Magnitude)')
        sar_plot_ax.legend()
        plt.tight_layout()
        plt.show()
    else:
        # Prepare 2D data for imshow, ensuring it's MAX_SAR_FRAMES rows with padding if needed
        sar_data_2d = np.zeros((MAX_SAR_FRAMES, IFFT_POINTS))
        # Place current accumulated data into the bottom of the buffer for visualization
        # The latest frame is at the top (highest y-index)
        num_current_frames = len(accumulated_cir_magnitudes)
        sar_data_2d[MAX_SAR_FRAMES - num_current_frames : MAX_SAR_FRAMES, :] = np.array(accumulated_cir_magnitudes).astype(float)
        
        sar_plot_image.set_data(sar_data_2d)
        
        # Adjust Y-axis limits dynamically based on current number of frames to scroll the view
        # We want to keep the current frame always visible and scrolling up
        if num_current_frames > MAX_SAR_FRAMES / 2: # Start scrolling when half full
             sar_plot_ax.set_ylim(num_current_frames - MAX_SAR_FRAMES / 2, num_current_frames + MAX_SAR_FRAMES / 2)
        else:
             sar_plot_ax.set_ylim(0, MAX_SAR_FRAMES) # Show full range initially

        # Update the extent of the image to reflect current number of frames
        # The extent y-values map to the original indices in the accumulated_cir_magnitudes deque
        sar_plot_image.set_extent([time_axis_ns_global[0], MAX_TOF_NS, 0, MAX_SAR_FRAMES])

        # Auto-scale color map (vmax) based on current max magnitude in the *displayed* data
        # Only use the part of the data that's actually being shown
        visible_data = sar_data_2d[MAX_SAR_FRAMES - num_current_frames : MAX_SAR_FRAMES, :]
        max_visible_magnitude = np.max(visible_data) if visible_data.size > 0 else 1.0
        sar_plot_image.set_clim(vmin=0, vmax=max_visible_magnitude * 1.1)
        
        # Update current frame indicator line
        current_frame_line.set_ydata([MAX_SAR_FRAMES - 1, MAX_SAR_FRAMES - 1]) # Always at the top of the fixed window
        current_frame_line.set_xdata([0, MAX_TOF_NS]) # Span the whole x-axis

        sar_plot_fig.canvas.draw()
        sar_plot_fig.canvas.flush_events()

if __name__ == '__main__':
    if sys.version_info < (3, 6):
        print(" Python version should >= 3.6")
        exit()
    parser = argparse.ArgumentParser(
        description="Read CSI data from serial port, compute CIR, and visualize a basic SAR-like image (RF Echo Map)."
    )
    parser.add_argument('-p', '--port', dest='port', action='store', required=True,
                        help="Serial port number of csv_recv device (e.g., COM3 or /dev/ttyUSB0)")
    parser.add_argument('-r', '--rate', dest='rate', type=int, default=10, 
                        help="Processing rate in Hz (how many packets per second to process).")
    args = parser.parse_args()
    
    serial_port = args.port
    processing_rate = args.rate

    print(f"--- RF Echo Map (Basic SAR) Visualization ---")
    print(f"CSIReader: Port {serial_port}, Rate {processing_rate} Hz.")
    print(f"Wi-Fi: {WIFI_BANDWIDTH_HZ/1e6:.0f} MHz Bandwidth, {NUM_RAW_SUBCARRIERS} Subcarriers.")
    print(f"Processing: Hamming Window, {CIR_SMOOTHING_WINDOW_SIZE}-pt Moving Avg, {CIR_MEDIAN_FILTER_KERNEL}-pt Median Filter, {CSI_PACKET_AVG_COUNT}-packet CSI Averaging.")
    print(f"Plot: Time of Flight up to {MAX_TOF_NS} ns ({MAX_TOF_NS * 0.3:.1f} meters). Displaying last {MAX_SAR_FRAMES} scan lines.")
    print("\n--- INSTRUCTIONS FOR VISUALIZATION ---")
    print("1. Start the script.")
    print("2. Move your drone/sensor steadily along a straight line, past objects.")
    print("3. Observe the graph:")
    print("   - The Y-axis (Scan Line Index) represents your movement/position over time.")
    print("   - The X-axis (Time of Flight) represents distance from the sensor (1ns ≈ 0.3m).")
    print("   - Bright spots are echoes/reflections.")
    print("   - **Look for CURVED 'SMILE' or 'FROWN' patterns!** These are stationary objects.")
    print("     The lowest point of the curve is when you were closest to the object.")
    print("   - A **straight vertical line** (especially near ToF=0) indicates a constant direct path (e.g., TX to RX on the drone) or a static internal artifact.")
    print("   - The **cyan horizontal line** shows the most recent scan line captured.")
    print("\nPress Ctrl+C in the terminal to stop the script.")
    print("---------------------------------------")

    reader = CSIReader(serial_port, raw_callback=process_and_accumulate_cir_for_sar, rate=processing_rate)
    
    try:
        reader.run() 
    except KeyboardInterrupt:
        print("\nExiting program. Closing plot...")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if sar_plot_fig:
            plt.close(sar_plot_fig)