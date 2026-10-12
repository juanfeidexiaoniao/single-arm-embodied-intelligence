import json
import yaml

class ActionPlanner:
    def __init__(self, registry_path, qwen_client):
        self.qwen_client = qwen_client
        # 加载策略注册表
        with open(registry_path, 'r', encoding='utf-8') as f:
            self.policy_data = json.load(f)
        
        # 将描述和 ID 组合成交给 LLM 看的上下文
        self.policy_context = self._build_policy_context()

    def _build_policy_context(self):
        ctx = []
        for policy_id, info in self.policy_data['policies'].items():
            ctx.append(f"- 【策略ID: {policy_id}】 策略描述: {info['description']}")
        return "\n".join(ctx)

    def _build_system_prompt(self):
        # 核心：定义 Agent 的角色、可调用能力和严格的输出格式
        system_prompt = f"""
        你是一个具身智能机器人的高层大脑。你的任务是根据用户的指令和当前场景描述，从提供的可用策略列表中选择合适的策略，并合理安排执行顺序。

        【可用策略列表 (只允许使用这里定义的ID)】
        {self.policy_context}

        【你的输出格式 (严格 JSON 格式，不要包含任何其他文本)】
        {{
          "thoughts": "你详细的思考过程和动作拆解逻辑。",
          "plan": ["policy_id_1", "policy_id_2"]
        }}

        【注意事项】
        1. 必须优先执行 go_home 初始化。
        2. 抓取物体前必须 open_gripper。
        3. 确保 plan 列表中的 ID 必须在策略注册表中。
        """
        return system_prompt

    def generate_plan(self, user_command, scene_desc):
        """调用 LLM 生成动作序列"""
        system_prompt = self._build_system_prompt()
        user_prompt = f"当前场景识别结果: {scene_desc}\n用户指令: {user_command}"
        
        llm_response = self.qwen_client.call_llm(system_prompt, user_prompt)
        
        # 尝试解析 JSON
        try:
            plan_json = json.loads(llm_response)
            return plan_json
        except json.JSONDecodeError:
            # 这是一个简单的容错：如果 JSON 解析失败，返回错误结构
            return {
                "thoughts": f"Error: LLM didn't return valid JSON. Response was: {llm_response}",
                "plan": []
            }