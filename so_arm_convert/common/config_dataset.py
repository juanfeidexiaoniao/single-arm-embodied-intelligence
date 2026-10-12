from dataclasses import dataclass
from typing import List, Tuple
import os
import yaml

@dataclass
class ResizeConfig:
    width: int
    height: int

@dataclass
class Config:
    # Basic settings
    joint_num: int  # 机械臂关节数量
    
    # Timeline settings
    train_hz: int
    main_timeline: str
    main_timeline_fps: int
    sample_drop: int
    
    # Processing flags
    is_binary: bool
    delta_action: bool
    relative_start: bool
    
    # Image resize settings
    resize: ResizeConfig

    # Task description
    task_description: str = "Pick and Place Task"

    @property
    def default_camera_names(self) -> List[str]:
        """返回你的RGB摄像头话题名称"""
        return ['rgb1', 'rgb2', 'rgb3']

    @property
    def slice_robot(self) -> List[Tuple[int, int]]:
        """返回机械臂关节索引范围"""
        return [(0, self.joint_num)]  # joint1~joint7

def load_config(config_path: str = None) -> Config:
    """加载配置文件"""
    if config_path is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, '..', 'lerobot_dataset.yaml')
        
    with open(config_path, 'r') as f:
        config_dict = yaml.safe_load(f)
    
    resize_config = ResizeConfig(
        width=config_dict['resize']['width'],
        height=config_dict['resize']['height']
    )
    
    return Config(
        joint_num=7,  # 你的机械臂7个关节
        train_hz=config_dict['train_hz'],
        main_timeline=config_dict.get('main_timeline', 'rgb1'),
        main_timeline_fps=config_dict['main_timeline_fps'],
        sample_drop=config_dict['sample_drop'],
        is_binary=config_dict['is_binary'],
        delta_action=config_dict['delta_action'],
        relative_start=config_dict['relative_start'],
        resize=resize_config,
        task_description=config_dict.get('task_description', "Pick and Place Task")
    )

# 默认配置实例
config = load_config()
