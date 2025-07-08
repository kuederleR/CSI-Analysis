from csi_py.csireader import CSIReader
import argparse
import sys
import matplotlib.pyplot as plt
import numpy as np

y_min = 0
y_max = 50
avg_history_len = 200

def moving_average(data, window_size):
    if len(data) < window_size:
        window = len(data)
    else:
        window = window_size
    return np.convolve(data, np.ones(window)/window, mode='same')

def graph_amplitude(arr):
    if not hasattr(graph_amplitude, "fig"):
        graph_amplitude.fig, (graph_amplitude.ax, graph_amplitude.ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=False)
        # Top: per-subcarrier amplitude
        graph_amplitude.line, = graph_amplitude.ax.plot(arr)
        graph_amplitude.smooth_line, = graph_amplitude.ax.plot(moving_average(arr, 10), color='orange', label='Smoothed')
        graph_amplitude.ax.set_title("CSI Amplitude")
        graph_amplitude.ax.set_xlabel("Subcarrier Index")
        graph_amplitude.ax.set_ylabel("Amplitude")
        graph_amplitude.ax.set_ylim(y_min, y_max)
        graph_amplitude.ax.legend()
        # Bottom: moving average
        graph_amplitude.avg_vals = []
        graph_amplitude.avg_line, = graph_amplitude.ax2.plot([])
        graph_amplitude.ax2.set_title("Average Amplitude (Moving, Last 200 Samples)")
        graph_amplitude.ax2.set_xlabel("Sample Index")
        graph_amplitude.ax2.set_ylabel("Average Amplitude")
        plt.ion()
        plt.tight_layout()
        plt.show()
    else:
        # Update top graph
        graph_amplitude.line.set_ydata(arr)
        graph_amplitude.line.set_xdata(np.arange(len(arr)))
        smooth = moving_average(arr, 10)
        graph_amplitude.smooth_line.set_ydata(smooth)
        graph_amplitude.smooth_line.set_xdata(np.arange(len(arr)))
        graph_amplitude.ax.relim()
        graph_amplitude.ax.autoscale_view()
        graph_amplitude.ax.set_ylim(y_min, y_max)
        # Update bottom graph
        avg = np.mean(arr)
        graph_amplitude.avg_vals.append(avg)
        if len(graph_amplitude.avg_vals) > avg_history_len:
            graph_amplitude.avg_vals = graph_amplitude.avg_vals[-avg_history_len:]
        graph_amplitude.avg_line.set_ydata(graph_amplitude.avg_vals)
        graph_amplitude.avg_line.set_xdata(np.arange(len(graph_amplitude.avg_vals)))
        graph_amplitude.ax2.relim()
        graph_amplitude.ax2.autoscale_view()
        graph_amplitude.fig.canvas.draw()
        graph_amplitude.fig.canvas.flush_events()

if __name__ == '__main__':
    if sys.version_info < (3, 6):
        print(" Python version should >= 3.6")
        exit()
    parser = argparse.ArgumentParser(
        description="Read CSI data from serial port and print the CSI array"
    )
    parser.add_argument('-p', '--port', dest='port', action='store', required=True,
                        help="Serial port number of csv_recv device")
    args = parser.parse_args()
    serial_port = args.port
    reader = CSIReader(serial_port, amplitude_callback=graph_amplitude, rate=10)
    reader.run()