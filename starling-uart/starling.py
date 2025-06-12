import serial
import time

# --- Configuration ---
# Set the serial port to match your system.

# J9 on the Starling board is connected to the ESP32's Serial2 (GPIO16 and GPIO17).
SERIAL_PORT = '/dev/ttyHS2'

# Set the baud rate to match the ESP32 script (115200)
BAUD_RATE = 115200

# --- Main Program ---
def read_from_uart():
    print(f"Attempting to open serial port: {SERIAL_PORT} at {BAUD_RATE} baud...")
    try:
        # Open the serial port
        # timeout=1 makes read_until and readline non-blocking for a short period
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print("Serial port opened successfully!")
        print("Waiting for data from ESP32...")

        while True:
            # Read a line from the serial port.
            # The ESP32 script uses Serial2.println(), which sends a newline character.
            # readline() reads until a newline character is received.
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                if line: # Only print if the line is not empty
                    print(f"Received: {line}")
            time.sleep(0.01) # Small delay to prevent busy-waiting and consume CPU

    except serial.SerialException as e:
        print(f"Error: Could not open or read from serial port '{SERIAL_PORT}'.")
        print(f"Please ensure the ESP32 is connected, powered on, and the correct port is selected.")
        print(f"Also, check permissions if on Linux (e.g., 'sudo usermod -a -G dialout $USER').")
        print(f"Details: {e}")
    except KeyboardInterrupt:
        print("\nExiting program.")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Serial port closed.")

if __name__ == "__main__":
    read_from_uart()
