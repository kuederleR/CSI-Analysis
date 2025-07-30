# odometry_tf_publisher.py
import rclpy
from rclpy.node import Node
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import TransformStamped
from px4_msgs.msg import VehicleOdometry # Make sure this message type is available in your ROS 2 workspace

class OdometryToTFPublisher(Node):
    """
    Subscribes to PX4 VehicleOdometry and publishes the dynamic transform
    from the 'odom' (world) frame to the drone's 'base_link' frame.
    """
    def __init__(self):
        super().__init__('odometry_tf_publisher')
        self.tf_broadcaster = TransformBroadcaster(self)
        self.initial_position = None  # Will be numpy array
        self.initial_orientation = None  # Will be numpy quaternion (w, x, y, z)
        self.subscription = self.create_subscription(
            VehicleOdometry,
            '/fmu/out/vehicle_odometry',
            self.odometry_callback,
            rclpy.qos.qos_profile_sensor_data
        )
        self.get_logger().info('Odometry to TF Publisher Node Started.')

    def odometry_callback(self, msg: VehicleOdometry):
        """
        Callback function for incoming VehicleOdometry messages.
        Publishes world->base_link as the pose relative to the world frame.
        """
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'world'
        t.child_frame_id = 'base_link'
        t.transform.translation.x = msg.position[0]
        t.transform.translation.y = msg.position[1]
        t.transform.translation.z = msg.position[2]
        t.transform.rotation.x = msg.q[0]
        t.transform.rotation.y = msg.q[1]
        t.transform.rotation.z = msg.q[2]
        t.transform.rotation.w = msg.q[3]

        self.tf_broadcaster.sendTransform(t)
        # self.get_logger().info(f'Published relative transform: {t.child_frame_id} from {t.header.frame_id}')

def main(args=None):
    rclpy.init(args=args)
    node = OdometryToTFPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()