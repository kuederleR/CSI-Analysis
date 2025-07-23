import rclpy
from rclpy.node import Node
from wifi_msgs.msg import CSI
from csi_py.csireader import CSIReader

CSI_SERIAL_PORT = '/dev/ttyHS2'  # Default serial port

class CSIPublisher(Node):
    def __init__(self, port):
        super().__init__('csi_publisher')
        self.publisher_ = self.create_publisher(CSI, 'csi_data', 10)
        self.reader = CSIReader(port, data_callback=self.publish_csi_data, rate=20)
        self.get_logger().info(f"CSI Publisher initialized on port {port}")

    def publish_csi_data(self, data):
        msg = CSI()
        msg.mac = str(data.meta['mac'])
        msg.rssi = int(data.meta['rssi'])
        msg.channel = int(data.meta['channel'])
        msg.num_subcarriers = len(data.amplitude)

        msg.csi_complex = [float(x) for x in data.csi_raw_data]
        msg.amplitude = [float(x) for x in data.amplitude]
        msg.phase = [float(x) for x in data.phase]

        self.publisher_.publish(msg)
        self.get_logger().info(f"Published CSI data with RSSI: {data.meta['rssi']}")

    def run(self):
        try:
            self.reader.run()
        except KeyboardInterrupt:
            self.reader.stop()
            self.get_logger().info("CSI Publisher stopped.")

def main(args=None):
    rclpy.init(args=args)
    port = CSI_SERIAL_PORT
    csi_publisher = CSIPublisher(port)
    # rclpy.spin(csi_publisher)
    try:
        csi_publisher.run()
    except Exception as e:
        csi_publisher.get_logger().error(f"Error occurred: {e}")
    rclpy.shutdown()