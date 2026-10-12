import sys
import os
import asyncio
from modules.qwen_client import QwenClient
from modules.perception import PerceptionModule
from modules.planner import ActionPlanner
from modules.executor import ActionExecutor
from modules.tg_bot import TelegramBot

class EmbodiedAgent:
    def __init__(self, config_dir):
        config_path = os.path.join(config_dir, 'config.yaml')
        registry_path = os.path.join(config_dir, 'policy_registry.json')

        # 实例化所有模块
        self.qwen_client = QwenClient(config_path)
        self.perception = PerceptionModule(config_path, self.qwen_client)
        self.planner = ActionPlanner(registry_path, self.qwen_client)
        self.executor = ActionExecutor(registry_path)

    async def process_user_command(self, user_command, feedback_callback):
        """Agent 主循环的核心逻辑"""
        # 1. 感知
        scene_desc, image_path = self.perception.capture_and_recognize()
        if "Error" in scene_desc:
            return scene_desc

        # 2. 将 VLM 识别出的图片发给用户
        # （因为 feedback_callback 期望的是 async，所以这里需要这样调用）
        # 这里为了简化，只发描述。真实项目可以通过 context.bot.send_photo
        
        # 3. 规划
        plan_json = self.planner.generate_plan(user_command, scene_desc)
        thoughts = plan_json.get("thoughts", "No thoughts.")
        plan = plan_json.get("plan", [])

        await feedback_callback(f"VLM 场景识别：{scene_desc}\n\nQwen 思考过程：{thoughts}\n\n规划策略序列：{plan}")

        if not plan:
            return "规划失败或无需动作。"

        # 4. 执行
        # 由于 subprocess 是同步的，可能会卡住 async loop，最好放在 run_in_executor
        success, failed_at = self.executor.execute_plan(plan, feedback_callback=None) # 这里传入反馈会让 subprocess 卡住，简化一下

        if success:
            return "所有动作顺利执行完毕！"
        else:
            return f"任务在策略 {failed_at} 执行时中断。"

if __name__ == "__main__":
    # 设置工作目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)
    
    config_dir = os.path.join(project_root, 'config')
    
    agent = EmbodiedAgent(config_dir)
    bot = TelegramBot(os.path.join(config_dir, 'config.yaml'), agent)
    
    print("[+] Agent is running...")
    bot.run()