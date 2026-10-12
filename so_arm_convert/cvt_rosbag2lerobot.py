#!/usr/bin/env python3
"""
ROS2 rosbag2 (.db3) to LeRobot dataset converter for a 7-DOF robotic arm with 3 RGB cameras.
"""

import dataclasses
from pathlib import Path
import shutil
import os
import numpy as np
import torch
import tqdm
import cv2
from collections import defaultdict

from lerobot.common.datasets.lerobot_dataset import LEROBOT_HOME, LeRobotDataset

# ROS2 rosbag2 API
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions

# ================= 机械臂配置 =================
JOINT_NAMES = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "joint7"]
CAMERA_TOPICS = ["rgb1", "rgb2", "rgb3"]
TRAIN_HZ = 20
RESIZE_W, RESIZE_H = 640, 480

@dataclasses.dataclass(frozen=True)
class DatasetConfig:
    use_videos: bool = True
    tolerance_s: float = 0.0001
    image_writer_processes: int = 4
    image_writer_threads: int = 2
    video_backend: str | None = None

DEFAULT_DATASET_CONFIG = DatasetConfig()

# ================= ROS2 rosbag2 读取 =================
class ArmRosbag2Reader:
    def __init__(self):
        self.topic_map = {
            "observation.state": {"topic": "/isaac_joint_states"},
            "action": {"topic": "/isaac_joint_command"}
        }
        for cam in CAMERA_TOPICS:
            self.topic_map[f"observation.images.{cam}"] = {"topic": f"/{cam}"}

    def process_rosbag(self, bag_path: str):
        storage_options = StorageOptions(uri=bag_path, storage_id='sqlite3')
        converter_options = ConverterOptions('', '')
        reader = SequentialReader()
        reader.open(storage_options, converter_options)

        data = defaultdict(list)
        while reader.has_next():
            (topic, serialized_msg, t) = reader.read_next()
            t_sec = t / 1e9  # ROS2 时间戳是纳秒
            topic_name = None
            for key, info in self.topic_map.items():
                if info["topic"] == topic:
                    topic_name = key
                    break
            if topic_name is None:
                continue

            # 修复：正确解析消息类型
            import rclpy.serialization
            from sensor_msgs.msg import Image, JointState
            
            try:
                if 'state' in topic_name or 'action' in topic_name:
                    msg = rclpy.serialization.deserialize_message(serialized_msg, JointState)
                else:
                    # 使用 Image 而不是 CompressedImage
                    msg = rclpy.serialization.deserialize_message(serialized_msg, Image)

                if "images" in topic_name:
                    # 修复：正确处理 sensor_msgs/Image
                    # 打印调试信息
                    print(f"处理图像话题: {topic_name}, 编码格式: {msg.encoding}, 尺寸: {msg.width}x{msg.height}")
                    
                    # 根据编码格式处理图像数据
                    if msg.encoding in ['rgb8', 'bgr8', 'rgba8', 'bgra8']:
                        # RGB/BGR 格式
                        channels = 3 if msg.encoding in ['rgb8', 'bgr8'] else 4
                        img = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, channels)
                        
                        # 修复：确保输出为RGB格式
                        if msg.encoding == 'rgb8':
                            # 已经是RGB格式，不需要转换
                            pass  # 保持RGB格式
                        elif msg.encoding == 'bgr8':
                            # BGR转RGB
                            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        elif msg.encoding == 'rgba8':
                            # RGBA转RGB
                            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
                        elif msg.encoding == 'bgra8':
                            # BGRA转RGB
                            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                    elif msg.encoding == 'mono8' or msg.encoding == '8UC1':
                        # 灰度图像转RGB
                        img = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width)
                        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
                    else:
                        # 默认处理，假设是RGB格式
                        print(f"警告: 未知的图像编码格式: {msg.encoding}, 使用默认处理")
                        img = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)
                        # 如果通道数>3，取前3个通道
                        if img.shape[2] > 3:
                            img = img[:, :, :3]
                    
                    # 调整尺寸
                    img = cv2.resize(img, (RESIZE_W, RESIZE_H))
                    frame = {"data": img, "timestamp": t_sec}
                else:
                    # 关节状态数据
                    frame = {"data": np.array(msg.position, dtype=np.float32), "timestamp": t_sec}

                data[topic_name].append(frame)
                
            except Exception as e:
                print(f"警告: 跳过损坏的消息 {topic_name}: {e}")
                continue

        # 对齐帧
        aligned_data = self.align_frames(data)
        return aligned_data

    def align_frames(self, data):
        """对齐不同话题的时间戳"""
        main_cam = CAMERA_TOPICS[0]
        timestamps = [f["timestamp"] for f in data[f"observation.images.{main_cam}"]]
        aligned = defaultdict(list)

        for t in timestamps:
            for key, frames in data.items():
                if len(frames) == 0:
                    continue
                frame_times = np.array([f["timestamp"] for f in frames])
                idx = np.argmin(np.abs(frame_times - t))
                if np.abs(frame_times[idx] - t) < 0.1:  # 100ms 容忍度
                    aligned[key].append(frames[idx])
                else:
                    # 如果没有接近的时间戳，跳过这一帧
                    print(f"警告: 话题 {key} 在时间 {t} 附近没有数据")
        
        # 检查对齐后的数据长度
        min_length = min(len(frames) for frames in aligned.values()) if aligned else 0
        if min_length == 0:
            print("错误: 没有成功对齐的数据")
            return {}
            
        # 确保所有话题数据长度一致
        for key in list(aligned.keys()):
            aligned[key] = aligned[key][:min_length]
            
        print(f"成功对齐 {min_length} 帧数据")
        return aligned

    def list_bag_files(self, bag_dir: str):
        return sorted(Path(bag_dir).glob("*.db3"))

# ================= 数据集创建 =================
def create_dataset(repo_id: str, root: str) -> LeRobotDataset:
    features = {
        "observation.state": {
            "dtype": "float32",
            "shape": (len(JOINT_NAMES),),
            "names": {"motors": JOINT_NAMES},
        },
        "action": {
            "dtype": "float32",
            "shape": (len(JOINT_NAMES),),
            "names": {"motors": JOINT_NAMES},
        },
    }

    for cam in CAMERA_TOPICS:
        features[f"observation.images.{cam}"] = {
            "dtype": "video",
            "shape": (3, RESIZE_H, RESIZE_W),
            "names": ["channels", "height", "width"],
        }

    if Path(LEROBOT_HOME / repo_id).exists():
        shutil.rmtree(LEROBOT_HOME / repo_id)

    dataset = LeRobotDataset.create(
        repo_id=repo_id,
        fps=TRAIN_HZ,
        robot_type="7dof_arm",
        features=features,
        use_videos=DEFAULT_DATASET_CONFIG.use_videos,
        tolerance_s=DEFAULT_DATASET_CONFIG.tolerance_s,
        image_writer_processes=DEFAULT_DATASET_CONFIG.image_writer_processes,
        image_writer_threads=DEFAULT_DATASET_CONFIG.image_writer_threads,
        video_backend=DEFAULT_DATASET_CONFIG.video_backend,
        root=root,
    )
    return dataset

# ================= 数据填充 =================
def populate_dataset(dataset: LeRobotDataset, bag_files: list[Path], task_name: str):
    reader = ArmRosbag2Reader()
    failed_bags = []

    # 预期的数据键
    EXPECTED_KEYS = ["observation.state", "action"] + [
        f"observation.images.{cam}" for cam in CAMERA_TOPICS
    ]

    for bag_file in tqdm.tqdm(bag_files):
        try:
            print(f"处理bag文件: {bag_file}")
            data = reader.process_rosbag(str(bag_file))

            if not data:
                print(f"警告: {bag_file} 没有有效数据")
                continue

            # 防御性检查：确保所有预期的键都存在
            missing_keys = [k for k in EXPECTED_KEYS if k not in data or len(data[k]) == 0]
            if missing_keys:
                print(f"警告: {bag_file} 缺少以下话题数据: {missing_keys}")
                failed_bags.append(str(bag_file))
                continue

            # 检查数据长度
            num_frames = len(data["observation.state"])
            print(f"从 {bag_file} 提取了 {num_frames} 帧数据")

            for i in range(num_frames):
                frame = {
                    "observation.state": torch.from_numpy(data["observation.state"][i]["data"]).float(),
                    "action": torch.from_numpy(data["action"][i]["data"]).float(),
                }
                for cam in CAMERA_TOPICS:
                    frame[f"observation.images.{cam}"] = data[f"observation.images.{cam}"][i]["data"]
                dataset.add_frame(frame)

            # 关键修复：encode_videos=False，避免 ffmpeg CXXABI 不兼容导致 buffer 脏状态
            dataset.save_episode(task=task_name, encode_videos=False)
            print(f"成功保存 {bag_file} 的数据")

        except Exception as e:
            print(f"❌ Failed {bag_file}: {e}")
            failed_bags.append(str(bag_file))
            # 关键修复：失败后重置 episode_buffer，防止级联污染下一个 bag
            dataset.clear_episode_buffer()
            continue

    if failed_bags:
        with open("failed_bags.txt", "w") as f:
            f.writelines("\n".join(failed_bags))
        print(f"❌ {len(failed_bags)} bags failed, saved to failed_bags.txt")

    if dataset.meta.total_episodes == 0:
        print("❌ 没有成功保存任何 episode，跳过 consolidate")
        return dataset

    # 修复 ffmpeg CXXABI 问题：临时切换到 conda 环境的 libstdc++
    # 系统 libstdc++ 缺少 CXXABI_1.3.15，ffmpeg 子进程需要
    orig_ld_preload = os.environ.pop("LD_PRELOAD", None)
    conda_libstdcpp = os.path.expanduser("~/miniconda3/envs/lerobot/lib/libstdc++.so.6")
    if os.path.exists(conda_libstdcpp):
        print(f"[INFO] 设置 LD_PRELOAD={conda_libstdcpp} 用于视频编码")
        os.environ["LD_PRELOAD"] = conda_libstdcpp

    try:
        dataset.consolidate()
    finally:
        # 恢复原始 LD_PRELOAD
        if orig_ld_preload:
            os.environ["LD_PRELOAD"] = orig_ld_preload

    return dataset

# ================= 主函数 =================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--raw_dir", required=True, type=str, help="Path to raw ROS bag2 (.db3) directory")
    parser.add_argument("--task_name", default="DEBUG", type=str)
    parser.add_argument("--repo_id", default="lerobot/7dof_arm", type=str)
    parser.add_argument("--root", required=True, type=str, help="LeRobot dataset root path")
    args = parser.parse_args()

    reader = ArmRosbag2Reader()
    bag_files = reader.list_bag_files(args.raw_dir)

    if not bag_files:
        print(f"错误: 在目录 {args.raw_dir} 中没有找到 .db3 文件")
        exit(1)

    print(f"找到 {len(bag_files)} 个bag文件: {[f.name for f in bag_files]}")

    dataset = create_dataset(args.repo_id, args.root)
    populate_dataset(dataset, bag_files, task_name=args.task_name)
    
    print("转换完成！")