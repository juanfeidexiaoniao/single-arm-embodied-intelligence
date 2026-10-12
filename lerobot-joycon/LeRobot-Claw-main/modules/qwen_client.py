import dashscope
from dashscope import MultiModalConversation, Generation
import os
import json

class QwenClient:
    def __init__(self, config_path):
        self.api_key = os.environ["DASHSCOPE_API_KEY"]
        dashscope.api_key = self.api_key

    def call_vlm(self, image_path, prompt="请详细描述图片中的场景，包括所有物体及其相对位置。"):
        """调用 Qwen-VL 进行场景识别"""
        messages = [{
            'role': 'user',
            'content': [
                {'image': f'file://{image_path}'},
                {'text': prompt},
            ]
        }]
        response = MultiModalConversation.call(model='qwen-vl-plus', messages=messages)
        
        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            return f"VLM Error: {response.code} - {response.message}"

    def call_llm(self, system_prompt, user_prompt):
        """调用 Qwen LLM 进行动作规划"""
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]
        response = Generation.call(
            model='qwen-plus', 
            messages=messages, 
            result_format='message'
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            return f"LLM Error: {response.code} - {response.message}"