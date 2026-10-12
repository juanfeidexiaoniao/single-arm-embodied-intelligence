#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32  # 根据你的实际消息类型修改

class StartPublisher(Node):
    def __init__(self):
        super().__init__('start_sub')
        self.publisher_ = self.create_publisher(Int32, '/start_sub', 10)
        self.get_logger().info("准备就绪：按 Enter 键发布消息（Ctrl+C 退出）")

    def publish_message(self):
        msg = Int32()
        msg.data = 1
        self.publisher_.publish(msg)
        self.get_logger().info('已发布消息: "%s"' % msg.data)


def main(args=None):
    rclpy.init(args=args)
    node = StartPublisher()

    try:
        while rclpy.ok():
            input()  # 等待用户按下 Enter
            node.publish_message()
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
