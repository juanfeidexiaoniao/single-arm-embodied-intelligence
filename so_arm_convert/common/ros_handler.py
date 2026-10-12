import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState, CompressedImage
from multiprocessing import Process, Queue
import json
import numpy as np
import cv2

class ROS2Handler(Node):
    def __init__(self, queue):
        super().__init__('ros2_handler')
        self.queue = queue
        self.topics_config = [
            ('/isaac_joint_states', JointState),
            ('/isaac_joint_command', JointState),
            ('/rgb1', CompressedImage),
            ('/rgb2', CompressedImage),
            ('/rgb3', CompressedImage),
        ]
        # 创建订阅
        for topic_name, msg_type in self.topics_config:
            self.create_subscription(
                msg_type,
                topic_name,
                lambda msg, tn=topic_name: self._generic_callback(msg, tn),
                10
            )

    def _extract_data(self, msg, topic_name):
        """提取消息数据"""
        if isinstance(msg, JointState):
            return list(msg.position)
        elif isinstance(msg, CompressedImage):
            # 转成numpy array
            img_arr = np.frombuffer(msg.data, dtype=np.uint8)
            cv_img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
            cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            return cv_img.tolist()  # 转成list方便queue序列化
        return {}

    def _get_timestamp(self, msg):
        try:
            return msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        except AttributeError:
            import time
            return time.time()

    def _generic_callback(self, msg, topic_name):
        message = {
            'type': topic_name,
            'data': self._extract_data(msg, topic_name),
            'timestamp': self._get_timestamp(msg)
        }
        self.queue.put(json.dumps(message))

def start_ros_handler(queue):
    rclpy.init()
    node = ROS2Handler(queue)
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

def get_ros_queue(maxsize=10):
    queue = Queue(maxsize=maxsize)
    p = Process(target=start_ros_handler, args=(queue,))
    p.start()
    return queue, p

if __name__ == "__main__":
    queue, p = get_ros_queue()
    try:
        import time
        while True:
            time.sleep(1)
            print("Queue size:", queue.qsize())
    except KeyboardInterrupt:
        p.terminate()
        p.join()
