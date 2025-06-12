#!/usr/bin/env python3
# -*-coding:utf-8-*-

# Copyright 2021 Espressif Systems (Shanghai) PTE LTD
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# This script reads Channel State Information (CSI) data from a serial port,
# processes it to calculate the A_CSI metric as described in the paper
# "Adversarial Occupancy Monitoring using One-Sided Through-Wall WiFi Sensing",
# and then plots the A_CSI values over time using PyQtGraph.

import sys
import csv
import json
import argparse
import numpy as np
import serial
from io import StringIO

from PyQt5.Qt import *
from pyqtgraph import PlotWidget
from PyQt5 import QtCore
import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal, QThread

##############################################################################
#                        CONFIGURABLE PARAMETERS                             #
# These parameters directly influence the A_CSI calculation based on the     #
# methodology described in the paper. Experiment with these values           #
# to find the best performance for your environment.                         #
##############################################################################

# Buffer size for storing A_CSI data points to display on the graph.
# This determines how many historical A_CSI values are kept and plotted.
CSI_DATA_INDEX = 200

# Maximum expected number of CSI data columns (subcarriers * 2, for real and imag parts).
# For ESP32, this can be up to 512 for 802.11n (256 subcarriers * 2).
# A common value seen for 40MHz bandwidth is 128 or 256 for 20MHz.
# Original code used 490, which is a safe upper bound for common cases.
CSI_DATA_COLUMNS = 490 # This was the missing parameter.

# Window length for the outlier filter (w1 in paper, Equation 4).
# This defines the number of recent samples used to identify and filter outliers
# for each individual subcarrier's amplitude. A larger value provides more
# smoothing but might reduce responsiveness to rapid changes.
OUTLIER_FILTER_WINDOW_W1 = 5 # Example value, try increasing (e.g., 50, 100)

# Window length for statistical aggregation (w2 in paper, Equation 7).
# This defines the number of recent filtered amplitude samples used to
# calculate a 'noise metric' (standard deviation in this implementation)
# for each subcarrier. Paper suggests w1 = w2.
AGGREGATION_WINDOW_W2 = 5 # Example value, try increasing (e.g., 50, 100)

# Threshold for outlier detection (A standard deviations from the mean in paper).
# Any amplitude value for a subcarrier that deviates by more than this many
# standard deviations from the mean of its window (w1) is considered an outlier.
OUTLIER_THRESHOLD_STD_DEV = 2 # Common threshold, can be adjusted (e.g., 2.5, 4)

##############################################################################
#                         GLOBAL DATA STRUCTURES                             #
# These arrays store the processed CSI data and are updated in real-time.    #
##############################################################################

# Defines column names for different CSI data formats.
# The script primarily uses DATA_COLUMNS_NAMES.
DATA_COLUMNS_NAMES_C5C6 = ["type", "id", "mac", "rssi", "rate","noise_floor","fft_gain","agc_gain", "channel", "local_timestamp",  "sig_len", "rx_state", "len", "first_word", "data"]
DATA_COLUMNS_NAMES = ["type", "id", "mac", "rssi", "rate", "sig_mode", "mcs", "bandwidth", "smoothing", "not_sounding", "aggregation", "stbc", "fec_coding",
                      "sgi", "noise_floor", "ampdu_cnt", "channel", "secondary_channel", "local_timestamp", "ant", "sig_len", "rx_state", "len", "first_word", "data"]

# Stores complex CSI data for a fixed number of recent packets (CSI_DATA_INDEX).
# This is where the raw complex CSI values are buffered before processing.
csi_data_complex = np.zeros([CSI_DATA_INDEX, CSI_DATA_COLUMNS // 2], dtype=np.complex64) # Divide by 2 as CSI_DATA_COLUMNS is for real+imag parts

# Stores the calculated A_CSI values for plotting over time.
# This buffer will hold the A_CSI history that is displayed.
acsi_data_buffer = np.zeros([CSI_DATA_INDEX], dtype=np.float64)

# Histories for raw and filtered amplitudes for each subcarrier.
# `raw_amplitude_history` stores the 'w1' most recent raw amplitudes for each subcarrier
# `filtered_amplitude_history` stores the 'w2' most recent *filtered* amplitudes for each subcarrier
raw_amplitude_history = [[] for _ in range(CSI_DATA_COLUMNS // 2)] # Divide by 2 for subcarrier count
filtered_amplitude_history = [[] for _ in range(CSI_DATA_COLUMNS // 2)] # Divide by 2 for subcarrier count


##############################################################################
#                            GUI CLASS                                     #
# Defines the main PyQtGraph window for displaying the A_CSI plot.         #
##############################################################################

class csi_data_graphical_window(QWidget):
    """
    PyQtGraph window for displaying the A_CSI data over time.
    """
    def __init__(self):
        super().__init__()

        # Set the initial size of the window.
        self.resize(1280, 400)

        # Initialize the PlotWidget for A_CSI.
        self.plotWidget_acsi = PlotWidget(self)
        self.plotWidget_acsi.setGeometry(QtCore.QRect(0, 0, 1280, 400)) # Full window size
        self.plotWidget_acsi.addLegend()
        self.plotWidget_acsi.setTitle("$A_{CSI}$ Data") # Title for the plot (LaTeX-like for math)
        self.plotWidget_acsi.setLabel('left', '$A_{CSI}$')  # Y-axis label
        self.plotWidget_acsi.setLabel('bottom', 'Time (Cumulative Packet Count)')  # X-axis label

        # Create a curve item to plot the A_CSI data.
        self.acsi_curve = self.plotWidget_acsi.plot([], name="$A_{CSI}$", pen='b') # Blue pen for the curve

        # Set up a timer to periodically update the plot.
        # The update_data method will be called every 100 milliseconds.
        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(20)

    def update_curve_colors(self, color_list):
        """
        Placeholder method, not used for the A_CSI plot.
        Kept for compatibility with existing signal connections.
        """
        pass

    def update_data(self):
        """
        Updates the A_CSI plot with the latest data from the global buffer.
        This method is called by the QTimer.
        """
        self.acsi_curve.setData(acsi_data_buffer)


##############################################################################
#                        A_CSI CALCULATION FUNCTIONS                         #
# These functions implement the signal processing steps described in the     #
# paper for calculating the A_CSI metric.                                    #
##############################################################################

def calculate_mean(data_window):
    """
    Calculates the mean of a given data window (sub-array of numerical data).
    Used in Equation (5) and (8) of the paper.
    """
    if len(data_window) == 0:
        return 0
    return np.mean(data_window)

def calculate_std_dev(data_window):
    """
    Calculates the standard deviation of a given data window.
    Used in Equation (6) and (7) of the paper.
    """
    if len(data_window) == 0:
        return 0
    return np.std(data_window)

def outlier_filter(current_A_t_i, subcarrier_raw_history, window_w1, threshold_std_dev):
    """
    Applies an outlier filter to a single subcarrier's amplitude (Equation 4).
    If the current sample `current_A_t_i` is an outlier relative to the
    `window_w1` recent raw samples, it is replaced with the most recent
    'normal' sample from the history.
    """
    # Ensure there's enough data for a full window calculation.
    if len(subcarrier_raw_history) < window_w1:
        return current_A_t_i

    # Calculate mean and standard deviation over the most recent `window_w1` raw samples.
    mu = calculate_mean(subcarrier_raw_history[-window_w1:])
    sigma = calculate_std_dev(subcarrier_raw_history[-window_w1:])

    # Avoid division by zero if standard deviation is zero.
    if sigma == 0:
        return current_A_t_i

    # Check if the current sample is an outlier based on the threshold.
    if abs(current_A_t_i - mu) / sigma > threshold_std_dev:
        # If it's an outlier, replace it with the previous valid sample.
        # This approximates `A_t-1_i` from the paper, using the sample before the current one in the history.
        if len(subcarrier_raw_history) > 1:
            return subcarrier_raw_history[-2]
        else:
            return current_A_t_i # Fallback if not enough history for replacement
    else:
        return current_A_t_i # Not an outlier, return the current sample

def phi_aggregation(subcarrier_filtered_history, window_w2):
    """
    Applies the statistical aggregation function Phi (Φ) from Equation (7).
    This calculates a 'noise metric' for a single subcarrier over a time window `window_w2`.
    As per the paper, Φ(x) is set to the standard deviation σ(x).
    """
    # Ensure there's enough data for a full window calculation.
    if len(subcarrier_filtered_history) < window_w2:
        return 0 # Return 0 if not enough data to compute the metric
    
    # Calculate the standard deviation of the filtered amplitude history for this subcarrier.
    return calculate_std_dev(subcarrier_filtered_history[-window_w2:])

def psi_aggregation(subcarriers_metrics):
    """
    Applies the statistical aggregation function Psi (Ψ) from Equation (8).
    This aggregates the noise metrics from all subcarriers for a single time instance.
    As per the paper, Ψ(x) is set to the mean μ(x). This results in the A_CSI value.
    """
    if len(subcarriers_metrics) == 0:
        return 0
    return calculate_mean(subcarriers_metrics)


##############################################################################
#                          DATA PARSING FUNCTION                             #
# Handles reading raw CSI data from the serial port and performing the       #
# A_CSI calculation.                                                         #
##############################################################################

def csi_data_read_parse(port: str, csv_writer, log_file_fd):
    """
    Reads CSI data from the specified serial port, parses it,
    calculates A_CSI, and updates the global A_CSI buffer.

    Args:
        port (str): The serial port to read from (e.g., '/dev/ttyUSB0').
        csv_writer: A CSV writer object to save raw CSI data to a file.
        log_file_fd: A file descriptor for logging bad or incomplete serial data.
    """
    global csi_data_complex, acsi_data_buffer, raw_amplitude_history, filtered_amplitude_history

    # Initialize serial connection.
    ser = serial.Serial(port=port, baudrate=921600, bytesize=8, parity='N', stopbits=1)
    
    # Flag to print CSI data length once for informational purposes.
    csi_len_printed = False 

    if ser.isOpen():
        print("open success")
    else:
        print("open failed")
        ser.close() # Ensure port is closed on failure
        return

    while True:
        try:
            # Read a line from the serial port.
            strings = str(ser.readline())
            if not strings:
                continue # Skip empty lines

            # Clean up the string to remove Python's byte string literal prefixes/suffixes.
            strings = strings.lstrip('b\'').rstrip('\\r\\n\'')
            
            # Check if the line contains CSI_DATA.
            if 'CSI_DATA' not in strings:
                log_file_fd.write(strings + '\n') # Log non-CSI data
                log_file_fd.flush()
                continue

            # Parse the CSV part of the CSI data.
            csv_reader = csv.reader(StringIO(strings))
            csi_data = next(csv_reader)
            
            # The last element in the CSI data list is the JSON string of raw CSI values.
            # The third to last element is the length of the CSI data.
            csi_data_len = int(csi_data[-3]) 

            # Validate the number of elements in the parsed CSI data.
            # This check ensures the data structure matches expected formats.
            if len(csi_data) != len(DATA_COLUMNS_NAMES) and len(csi_data) != len(DATA_COLUMNS_NAMES_C5C6):
                print(f"element number is not equal {len(csi_data)} {len(DATA_COLUMNS_NAMES)}")
                log_file_fd.write("element number is not equal\n")
                log_file_fd.write(strings + '\n')
                log_file_fd.flush()
                continue

            # Attempt to parse the raw CSI JSON string.
            try:
                csi_raw_data = json.loads(csi_data[-1])
                print(f"csi_raw_data: {csi_raw_data}")
            except json.JSONDecodeError:
                print("data is incomplete or malformed JSON")
                log_file_fd.write("data is incomplete (JSON error)\n")
                log_file_fd.write(strings + '\n')
                log_file_fd.flush()
                continue
            
            # Validate the reported CSI data length against the parsed JSON array length.
            # The ESP32 provides CSI values as interleaved Imaginary and Real parts.
            # So, the `csi_data_len` (total elements in the JSON array) should be twice the number of subcarriers.
            if csi_data_len != len(csi_raw_data):
                print(f"csi_data_len is not equal {csi_data_len} (reported) vs {len(csi_raw_data)} (actual parsed)")
                log_file_fd.write("csi_data_len is not equal\n")
                log_file_fd.write(strings + '\n')
                log_file_fd.flush()
                continue
            

            # Write the full CSI data line to the CSV file.
            csv_writer.writerow(csi_data)

            # --- Update global CSI complex data buffer ---
            # Shift all existing data to the left to make space for the new data point.
            csi_data_complex[:-1] = csi_data_complex[1:]
            
            # Populate the last row of csi_data_complex with the new CSI values.
            # The raw CSI data contains interleaved imaginary and real parts (Imag, Real, Imag, Real...).
            # We process csi_data_len // 2 pairs to get complex numbers.
            # Ensure we don't exceed the buffer's capacity (CSI_DATA_COLUMNS // 2).
            num_subcarriers = min(csi_data_len // 2, csi_data_complex.shape[1])
            for i in range(num_subcarriers):
                # Complex number is (real_part + j * imaginary_part)
                # Raw data is [Imag0, Real0, Imag1, Real1, ...]
                csi_data_complex[-1][i] = complex(csi_raw_data[i * 2 + 1], csi_raw_data[i * 2])
            
            # --- CSI Pre-processing to calculate A_CSI ---
            # Get the absolute amplitude of the complex CSI values for the current packet.
            # We only consider the valid subcarriers reported in this packet.
            current_amplitudes = np.abs(csi_data_complex[-1, :num_subcarriers])
            
            # This list will store the intermediate "noise metrics" (sigma of filtered amplitudes)
            # for each subcarrier before the final aggregation into A_CSI.
            subcarrier_noise_metrics = []

            # Iterate through each valid subcarrier to apply filtering and aggregation.
            for i in range(num_subcarriers):
                # 1. Update Raw Amplitude History for this subcarrier (for outlier filter).
                # This history is truncated to `OUTLIER_FILTER_WINDOW_W1`.
                raw_amplitude_history[i].append(current_amplitudes[i])
                if len(raw_amplitude_history[i]) > OUTLIER_FILTER_WINDOW_W1:
                    raw_amplitude_history[i].pop(0)

                # 2. Apply Outlier Filter (Equation 4: A_bar_t_i).
                # This uses the raw history to decide if the current raw amplitude is an outlier.
                filtered_A_t_i = outlier_filter(
                    current_amplitudes[i],
                    raw_amplitude_history[i],
                    OUTLIER_FILTER_WINDOW_W1,
                    OUTLIER_THRESHOLD_STD_DEV
                )
                
                # 3. Update Filtered Amplitude History for this subcarrier (for Phi aggregation).
                # This history stores the values *after* outlier filtering and is truncated to `AGGREGATION_WINDOW_W2`.
                filtered_amplitude_history[i].append(filtered_A_t_i)
                if len(filtered_amplitude_history[i]) > AGGREGATION_WINDOW_W2:
                    filtered_amplitude_history[i].pop(0)

                # 4. Apply Phi Aggregation (Equation 7: A_tilde_t_i, which is sigma of A_bar_t_i window).
                # This calculates the 'noise metric' for the current subcarrier using its filtered history.
                subcarrier_noise_metric = phi_aggregation(
                    filtered_amplitude_history[i],
                    AGGREGATION_WINDOW_W2
                )
                subcarrier_noise_metrics.append(subcarrier_noise_metric)

            # 5. Apply Psi Aggregation (Equation 8: A_CSI,t).
            # This is the final step, taking the mean of all subcarrier noise metrics
            # for the current time instance to get the A_CSI value.
            A_CSI_t = psi_aggregation(subcarrier_noise_metrics)

            # --- Update global A_CSI data buffer for plotting ---
            # Shift existing A_CSI data to the left to make space for the new value.
            acsi_data_buffer[:-1] = acsi_data_buffer[1:]
            # Add the newly calculated A_CSI value to the end of the buffer.
            acsi_data_buffer[-1] = A_CSI_t

            # Print CSI data length once for confirmation.
            if not csi_len_printed:
                print("CSI data length:", csi_data_len)
                csi_len_printed = True

        except Exception as e:
            # Catch any unexpected errors during processing and log them.
            print(f"An error occurred during data processing: {e}")
            log_file_fd.write(f"Error processing line: {strings.strip()} - {e}\n")
            log_file_fd.flush()
            continue # Continue to the next line

    ser.close() # Close serial port when loop breaks (e.g., serial connection lost)


##############################################################################
#                             SUB-THREAD CLASS                               #
# Runs the serial port reading and CSI parsing in a separate thread to keep  #
# the GUI responsive.                                                        #
##############################################################################

class SubThread (QThread):
    # This signal is still defined but `update_curve_colors` method in GUI
    # is a placeholder as colors are not directly used for the A_CSI plot.
    data_ready = pyqtSignal(object)

    def __init__(self, serial_port, save_file_name, log_file_name):
        super().__init__()
        self.serial_port = serial_port

        # Open files for saving raw CSI data and logging errors/non-CSI data.
        save_file_fd = open(save_file_name, 'w')
        self.log_file_fd = open(log_file_name, 'w')
        
        # Initialize CSV writer for the raw CSI data file.
        self.csv_writer = csv.writer(save_file_fd)
        self.csv_writer.writerow(DATA_COLUMNS_NAMES) # Write header row

    def run(self):
        """
        The main method executed when the thread starts.
        Calls the CSI data reading and parsing function.
        """
        # Call the data parsing function without the unused callback for A_CSI plotting.
        csi_data_read_parse(self.serial_port, self.csv_writer, self.log_file_fd)

    def __del__(self):
        """
        Destructor for the thread. Ensures the log file is closed cleanly.
        """
        self.wait() # Wait for the thread to finish execution
        self.log_file_fd.close() # Close the log file


##############################################################################
#                                MAIN EXECUTION                              #
# Entry point of the script. Sets up the application, thread, and GUI.       #
##############################################################################

if __name__ == '__main__':
    # Check Python version compatibility.
    if sys.version_info < (3, 6):
        print("Python version should be >= 3.6")
        sys.exit(1) # Exit with an error code

    # Set up argument parser for command-line arguments.
    parser = argparse.ArgumentParser(
        description="Read CSI data from serial port and display A_CSI graphically")
    parser.add_argument('-p', '--port', dest='port', action='store', required=True,
                        help="Serial port number of csv_recv device (e.g., COM3 or /dev/ttyUSB0)")
    parser.add_argument('-s', '--store', dest='store_file', action='store', default='./csi_data.csv',
                        help="Path to save the raw CSI data printed by the serial port")
    parser.add_argument('-l', '--log', dest="log_file", action="store", default="./csi_data_log.txt",
                        help="Path to save other serial data and bad CSI data to a log file")

    # Parse command-line arguments.
    args = parser.parse_args()
    serial_port = args.port
    file_name = args.store_file
    log_file_name = args.log_file

    # Initialize the PyQt application.
    app = QApplication(sys.argv)

    # Create an instance of the SubThread to handle serial communication.
    subthread = SubThread(serial_port, file_name, log_file_name)

    # Create an instance of the graphical window.
    window = csi_data_graphical_window()
    
    # Connect the data_ready signal (though not directly used for A_CSI plot content).
    # This connection is harmless as update_curve_colors is a no-op currently.
    subthread.data_ready.connect(window.update_curve_colors) 
    
    # Start the background thread.
    subthread.start()
    
    # Show the GUI window.
    window.show()

    # Start the PyQt event loop.
    sys.exit(app.exec())