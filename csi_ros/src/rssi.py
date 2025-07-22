import sys
from csi_py.csireader import CSIReader


def print_rssi(data):
    print(f"RSSI: {data.meta['rssi']}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <serial_port>")
        sys.exit(1)
    port = sys.argv[1]
    reader = CSIReader(port, data_callback=print_rssi, rate=20)
    try:
        reader.run()
    except KeyboardInterrupt:
        reader.stop()
        print("Stopped.")

if __name__ == "__main__":
    main()