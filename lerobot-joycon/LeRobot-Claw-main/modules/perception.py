import cv2
import time
import os
import yaml
from datetime import datetime

class PerceptionModule:
    def __init__(self, config_path, qwen_client):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        self.camera_id = config.get('camera_id', 0)
        self.qwen_client = qwen_client
        self.base_dir = "data/photos"
        os.makedirs(self.base_dir, exist_ok=True)

    def capture_and_recognize(self):
        """抓取当前画面，保存并发送给 Qwen-VL"""
        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            return "Error: Cannot open camera.", None

        # 给相机几帧时间来调整曝光
        for _ in range(5):
            ret, frame = cap.read()
        
        if not ret:
            cap.release()
            return "Error: Cannot capture frame.", None

        # 保存图片
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_name = f"{timestamp}.jpg"
        image_path = os.path.join(self.base_dir, image_name)
        cv2.imwrite(image_path, frame)
        cap.release()

        # 调用 VLM 识别场景
        scene_desc = self.qwen_client.call_vlm(image_path)
        return scene_desc, image_pathh
