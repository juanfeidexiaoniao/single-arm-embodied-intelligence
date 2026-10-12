# 大一年度项目：单臂操作自主具身智能系统设计

单机械臂操作与具身智能实验项目的源码快照，包括 LeRobot / Joy-Con 遥操作、自然语言与视觉交互、ROS 2 接口、数据采集与转换、MoveIt 配置及 Isaac Sim 仿真资源。

## 目录

| 目录 | 内容 |
| --- | --- |
| `lerobot-joycon/` | LeRobot 控制、遥操作、训练与推理脚本，语音控制实验，以及 Qwen + Telegram Agent |
| `lerobot_ros2/` | ROS 2 相机与机械臂插件、示例及已包含的依赖源码 |
| `so_arm_convert/` | ROS bag 采集与 LeRobot 数据格式转换工具 |
| `so-arm_moveit_isaacsim_ws/` | MoveIt 配置与机械臂 USD 模型 |
| `simulation/` | 六自由度机械臂 ROS 2 工作空间源码、URDF / STL 与仿真场景 |

## 使用说明

各模块依赖与入口见所在目录的 README。此仓库保留了实验脚本及上游依赖的现有结构，不代表所有实验均可在同一环境直接运行。

- LeRobot / Joy-Con：见 `lerobot-joycon/README.md`、`Single_tutorial.md` 与 `Double_tutorial.md`。
- ROS 2 插件：见 `lerobot_ros2/README.md`。`submodules/` 内以普通目录保存源码快照，不需要再次拉取 Git 子模块；安装时可使用 `init.sh` 的环境与安装选项。
- 数据转换：见 `so_arm_convert/readme.md`；输入 ROS bag 与输出数据集需自行准备。
- 仿真：见 `simulation/read.md`。场景原有的本地外部资源引用已将用户名替换为 `user`，须按本机资源位置重新配置；部分原始场景依赖未包含在提供的项目文件夹内。
- 训练与推理：数据集和检查点需自行准备，并调整脚本中的相机、串口、数据与模型路径。

## API 与 Agent 配置

所有上传的凭据都使用本地环境变量，实际值不写入仓库：

| 环境变量 | 使用位置 |
| --- | --- |
| `DASHSCOPE_API_KEY` | DashScope / Qwen 语音与视觉实验、LeRobot-Claw Agent |
| `SPARK_API_KEY` | 讯飞 Spark 语音控制实验 |
| `TELEGRAM_BOT_TOKEN` | LeRobot-Claw Telegram 入口 |

使用 Agent 前，在 `lerobot-joycon/LeRobot-Claw-main/` 中运行：

```bash
cp config/config.yaml.example config/config.yaml
```

在本地设置所需环境变量，再调整相机配置与策略注册表。`config/config.yaml` 已加入忽略规则。

## 上传范围

公开版本包含代码、技术文档、依赖声明、机器人模型与仿真资源。原项目中的本地采集图像、视频、音频、ROS bag、数据集、训练权重、运行日志、缓存、构建安装产物、编辑器配置及旧 Git 历史没有上传。详细说明见 `PUBLIC_EXPORT.md`。

## 来源与许可

本项目包含第三方开源源码与资源，保留各目录的原始 LICENSE、版权声明与上游说明；不另行将所有内容统一改为一种许可证。使用与再分发时请分别遵循相关目录的许可。
