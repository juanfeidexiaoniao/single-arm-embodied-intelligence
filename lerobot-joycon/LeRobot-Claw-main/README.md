# LeRobot-Claw: Embodied AI Agent (Qwen + LeRobot + Telegram)

[English](#english-version) | [中文说明](#中文说明)

---

<a id="english-version"></a>
## English Version

An Embodied AI Agent project built on Large Language/Vision Models (LLM/VLM) and the underlying robotic control framework.

This Agent receives natural language commands via Telegram, utilizes **Qwen-VL** to perceive and recognize the current scene in the robot's field of view, employs the **Qwen-Plus** "brain" for task decomposition, and finally maps the planned action sequence into low-level terminal commands for **LeRobot** to execute.

### Key Features

- **Natural Language Interaction**: Integrated with a Telegram Bot, allowing you to send commands and receive real-time visual/textual feedback from the robot anywhere.
- **Scene Perception (Perception Layer)**: Integrated with the Qwen-VL Vision-Language Model to dynamically understand the environment and object locations.
- **Action Planning (Cognition Layer)**: Zero-shot action decomposition based on LLMs, strictly outputting structured JSON policies.
- **Action Execution (Execution Layer)**: Deep integration with the HuggingFace `lerobot` framework. Seamlessly calls ACT (Action Chunking with Transformers) inference policies via a configuration mapping table.

### Directory Structure

```text
LeRobot-Claw/
├── main.py                     # Main entry point
├── config/
│   ├── config.yaml.example     # Camera configuration template (copy to config.yaml)
│   └── policy_registry.json    # Policy registry (Maps high-level semantics to LeRobot commands)
└── modules/                    # Core modules
    ├── perception.py           # Vision & Camera handling
    ├── planner.py              # LLM Action Planning
    ├── executor.py             # LeRobot subprocess execution
    ├── qwen_client.py          # API Client for Qwen VL/LLM
    └── tg_bot.py               # Telegram Bot interface
```

### Prerequisites & Installation

1. **Base Environment**: Ubuntu 22.04 and Miniconda are highly recommended.
2. **Install LeRobot**: Please refer to the official LeRobot documentation to install the base robotic framework.
3. **Clone & Install Dependencies**:

```bash
git clone https://github.com/juanfeidexiaoniao/single-arm-embodied-intelligence.git
cd single-arm-embodied-intelligence/lerobot-joycon/LeRobot-Claw-main
# Activate your lerobot conda environment
conda activate lerobot

# Install required packages
pip install -r requirements.txt
```

### Quick Start

1. Navigate to the `config/` directory, copy `config.yaml.example` and rename it to `config.yaml`.
2. Set the `DASHSCOPE_API_KEY` and `TELEGRAM_BOT_TOKEN` environment variables in your local shell. Credentials are never stored in this repository.
3. *(Optional)* If you are in a region requiring a proxy for Telegram, ensure your terminal proxy is set (e.g., `export https_proxy="http://127.0.0.1:7890"`).
4. Run the main program:

```bash
python main.py
```

5. Open Telegram, find your Bot, and send a command like: *"Help me put the red cube into the box."*

### Customizing the Policy Registry

You can freely define the skills the LLM can call in `config/policy_registry.json`. Modify the `command` field to point to your custom trained LeRobot evaluation scripts.

### License

This project is licensed under the MIT License.

---

<a id="中文说明"></a>
## 中文说明

这是一个基于大语言模型/视觉大模型 (LLM/VLM) 和底层机器人控制框架构建的具身智能体项目。

该 Agent 能够通过 Telegram 接收自然语言指令，利用 **Qwen-VL** 观察并识别当前机器人视野中的场景，通过 **Qwen-Plus** 大脑进行任务动作拆解，最终将规划好的动作序列映射为 **LeRobot** 的底层终端指令并执行。

### 核心特性

- **自然语言交互**：接入 Telegram Bot，随时随地发送指令并获取机器人状态和视觉反馈。
- **场景识别 (感知层)**：接入 Qwen-VL 视觉大模型，动态理解环境和物体相对位置。
- **动作规划 (认知层)**：基于 LLM 的零样本动作拆解，严格输出结构化的 JSON 策略序列。
- **动作执行 (执行层)**：与 HuggingFace `lerobot` 框架深度集成，通过配置映射表无缝调用推理策略。

### 目录结构

```text
LeRobot-Claw/
├── main.py                     # 主程序入口
├── config/
│   ├── config.yaml.example     # 相机配置模板 (复制为 config.yaml)
│   └── policy_registry.json    # 策略注册表 (高层语义映射到低层 LeRobot 指令)
└── modules/                    # 核心功能模块
    ├── perception.py           # 视觉捕获与识别
    ├── planner.py              # LLM 动作规划大脑
    ├── executor.py             # LeRobot 终端指令执行器
    ├── qwen_client.py          # Qwen 大模型接口封装
    └── tg_bot.py               # Telegram 交互逻辑
```

### 环境安装

1. **基础环境**：强烈推荐使用 Ubuntu 22.04 和 Miniconda 进行环境隔离。
2. **安装 LeRobot**：请参考 LeRobot 官方文档完成基础控制框架的安装和环境配置。
3. **克隆本项目并安装依赖**：

```bash
git clone https://github.com/你的用户名/你的项目名.git
cd LeRobot-Claw

# 激活你原有的 lerobot conda 环境
conda activate lerobot

# 安装本项目额外需要的依赖
pip install -r requirements.txt
```

### 快速启动

1. 进入 `config/` 目录，将 `config.yaml.example` 复制并重命名为 `config.yaml`。
2. 在本地终端设置 `DASHSCOPE_API_KEY`（阿里云百炼）和 `TELEGRAM_BOT_TOKEN`（BotFather）环境变量。实际凭据不写入配置文件。
3. **（国内环境必选）** 请确保运行终端配置了正确的网络代理，以保障 Telegram 正常通信：

```bash
export http_proxy="http://127.0.0.1:7890"
export https_proxy="http://127.0.0.1:7890"
export all_proxy="http://127.0.0.1:7890"
```

4. 运行主程序：

```bash
python main.py
```

5. 打开 Telegram，向你的 Bot 发送自然语言指令，例如：*"帮我把红色的方块放进盒子里"*。

### 自定义底层策略 (Policy Registry)

本项目的高度可扩展性体现在 `config/policy_registry.json` 中。你可以自由向 LLM 注册机器人的新技能，只需将 `command` 字段修改为你自己训练的 LeRobot 推理脚本即可实现无缝调用。

### 开源协议

本项目采用 **MIT License** 开源协议。

