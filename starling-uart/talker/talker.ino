// Define the RX and TX pins for UART2
// On most ESP32 Dev Modules, these are typically GPIO16 (RX2) and GPIO17 (TX2).
// You can change these if your specific board or wiring uses different pins.
#define RXD2 16
#define TXD2 17

// Variable to store the incrementing number
long counter = 0;

// Variable to store the last time a number was sent
unsigned long previousMillis = 0;

// Interval for sending data (0.5 seconds = 500 milliseconds)
const long interval = 500;

void setup() {
  // Initialize Serial (UART0) for debugging purposes.
  // This will print messages to the Arduino IDE Serial Monitor.
  Serial.begin(115200);
  while (!Serial); // Wait for Serial Monitor to open

  Serial.println("ESP32 UART2 Incrementing Counter");
  Serial.println("Initializing UART2 on pins RX:16, TX:17...");

  // Initialize Serial2 (UART2) with a baud rate of 115200.
  // The begin() function takes baud rate, serial config (e.g., SERIAL_8N1 for 8 data bits, no parity, 1 stop bit),
  // RX pin, and TX pin.
  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);

  Serial.println("UART2 initialized. Sending incrementing number...");
}

void loop() {
  // Get the current time
  unsigned long currentMillis = millis();

  // Check if the interval has passed
  if (currentMillis - previousMillis >= interval) {
    // Save the current time as the last time a message was sent
    previousMillis = currentMillis;

    // Increment the counter
    counter++;

    // Print the number to UART2
    Serial2.print("Counter: ");
    Serial2.println(counter);

    // Also print to Serial (UART0) for debugging in the Arduino IDE Serial Monitor
    Serial.print("Sent to UART2: Counter: ");
    Serial.println(counter);
  }
}
