#!/usr/bin/env python3
import numpy as np
import cv2
import rosbag
from pprint import pprint
import os
import glob
from collections import defaultdict

# ================ 机械臂关节定义 ================
DEFAULT_ARM_JOINT_NAMES = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "joint7"]

DEFAULT_JOINT_NAMES = {
    "full_joint_names": DEFAULT_ARM_JOINT_NAMES,
    "arm_joint_names": DEFAULT_ARM_JOINT_NAMES,
}

# ================ 配置参数 ================
# 图像 resize 尺寸
RESIZE_W = 640
RESIZE_H = 480

# 数据对齐参数
DEFAULT_CAMERA_NAMES = ['rgb1', 'rgb2', 'rgb3']
TRAIN_HZ = 10          # 训练频率
MAIN_TIMELINE_FPS = 30 # 原始帧率
SAMPLE_DROP = 0         # 可跳过前后帧数量
SLICE_ROBOT = [(0, 7)]  # 只取7个关节

# ================ 数据处理函数 ================
class MsgProcesser:
    @staticmethod
    def process_color_image(msg):
        """处理RGB图像消息"""
        if hasattr(msg, 'encoding'):
            if msg.encoding not in ['rgb8', 'bgr8']:
                raise ValueError(f"Unsupported encoding: {msg.encoding}")
            img_arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
            if msg.encoding == 'bgr8':
                cv_img = cv2.cvtColor(img_arr, cv2.COLOR_BGR2RGB)
            else:
                cv_img = img_arr
        else:
            # CompressedImage
            img_arr = np.frombuffer(msg.data, dtype=np.uint8)
            cv_img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
            if cv_img is None:
                raise ValueError("Failed to decode compressed image")
            cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        cv_img = cv2.resize(cv_img, (RESIZE_W, RESIZE_H))
        return {"data": cv_img, "timestamp": msg.header.stamp.to_sec()}

    @staticmethod
    def process_joint_state(msg):
        """处理 /isaac_joint_states"""
        joint_q = msg.position
        return {"data": np.array(joint_q), "timestamp": msg.header.stamp.to_sec()}

    @staticmethod
    def process_joint_cmd(msg):
        """处理 /isaac_joint_command"""
        joint_q = msg.position
        return {"data": np.array(joint_q), "timestamp": msg.header.stamp.to_sec()}

# ================ ROSBag 读取和处理 ================
class RosbagReader:
    def __init__(self):
        self._processer = MsgProcesser()
        self._topic_process_map = {
            "joint_states": {
                "topic": "/isaac_joint_states",
                "msg_process_fn": self._processer.process_joint_state,
            },
            "joint_commands": {
                "topic": "/isaac_joint_command",
                "msg_process_fn": self._processer.process_joint_cmd,
            },
        }
        # 添加RGB摄像头
        for camera in DEFAULT_CAMERA_NAMES:
            self._topic_process_map[camera] = {
                "topic": f"/{camera}",
                "msg_process_fn": self._processer.process_color_image,
            }

    def load_bag(self, bag_file: str):
        """加载rosbag文件"""
        try:
            bag = rosbag.Bag(bag_file)
            return bag
        except Exception as e:
            raise RuntimeError(f"Failed to load bag file {bag_file}: {e}")

    def process_rosbag(self, bag_file: str):
        """读取并处理rosbag"""
        bag = self.load_bag(bag_file)
        data = {}
        for key, topic_info in self._topic_process_map.items():
            topic = topic_info["topic"]
            process_fn = topic_info["msg_process_fn"]
            data[key] = []
            for _, msg, t in bag.read_messages(topics=topic):
                msg_data = process_fn(msg)
                # 使用bag时间戳
                msg_data["timestamp"] = t.to_sec()
                data[key].append(msg_data)
        aligned_data = self.align_data(data)
        return aligned_data

    def align_data(self, data: dict):
        """按主时间轴对齐数据"""
        aligned_data = defaultdict(list)
        main_cam = DEFAULT_CAMERA_NAMES[0]
        jump = max(MAIN_TIMELINE_FPS // TRAIN_HZ, 1)
        main_ts = [d['timestamp'] for d in data[main_cam]][SAMPLE_DROP:-SAMPLE_DROP:jump]
        min_end = min([data[k][-1]['timestamp'] for k in data.keys() if len(data[k]) > 0])
        main_ts = [t for t in main_ts if t < min_end]

        for stamp in main_ts:
            for key, v in data.items():
                if len(v) > 0:
                    ts_list = np.array([d['timestamp'] for d in v])
                    idx = np.argmin(np.abs(ts_list - stamp))
                    aligned_data[key].append(v[idx])
                else:
                    aligned_data[key] = []
        return aligned_data

    def list_bag_files(self, bag_dir: str):
        """列出目录下所有bag文件"""
        bag_files = glob.glob(os.path.join(bag_dir, '*.bag'))
        bag_files.sort()
        return bag_files

    def process_rosbag_dir(self, bag_dir: str):
        """批量处理目录下bag文件"""
        all_data = []
        bag_files = self.list_bag_files(bag_dir)
        for bf in bag_files:
            print(f"Processing {bf}")
            ep_data = self.process_rosbag(bf)
            all_data.append(ep_data)
        return all_data

# ================ 示例运行 ================
if __name__ == "__main__":
    bag_file = '/path/to/your/rosbag.bag'  # 修改为你的bag路径
    reader = RosbagReader()
    data_aligned = reader.process_rosbag(bag_file)
    
    print("Aligned keys:", data_aligned.keys())
    print("Example joint_states shape:", np.array(data_aligned["joint_states"][0]["data"]).shape)
    print("Example rgb1 shape:", np.array(data_aligned["rgb1"][0]["data"]).shape)
