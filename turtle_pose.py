import rclpy
from rclpy.node import Node

from turtlesim.msg import Pose
from math import degrees

class TurtlePose(Node):

    def __init__(self):
        super().__init__('turtle_pose')
        self.create_subscription(
            Pose,
            '/turtle1/pose',
            self.listener_callback,
            10)
        

    def listener_callback(self, msg):
        self.get_logger().info('theta= : "%s"' % degrees(msg.theta))


def main(args=None):
    rclpy.init(args=args)

    node = TurtlePose()

    rclpy.spin(node)

    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
