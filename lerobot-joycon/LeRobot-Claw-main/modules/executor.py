import json
import subprocess
import time

class ActionExecutor:
    def __init__(self, registry_path):
        with open(registry_path, 'r', encoding='utf-8') as f:
            self.policy_data = json.load(f)

    def execute_plan(self, plan_list, feedback_callback=None):
        """遍历并执行动作序列"""
        success_all = True
        failed_at = None

        for policy_id in plan_list:
            if policy_id in self.policy_data['policies']:
                command = self.policy_data['policies'][policy_id]['command']
                msg = f"[*] 正在执行策略: {policy_id}\n终端指令: {command}"
                print(msg)
                if feedback_callback:
                    feedback_callback(msg)

                # 在 Ubuntu 终端执行指令
                try:
                    # 使用 subprocess 运行，并捕获输出
                    process = subprocess.run(
                        command, 
                        shell=True,
                        check=True, # 如果非零退出码则抛出异常
                        capture_output=True, # 捕获 stdout 和 stderr
                        text=True, # 将输出作为文本
                        timeout=300 # 设置超时（例如5分钟）
                    )
                    
                    print(f"[+] 策略 {policy_id} 执行成功。")
                    if feedback_callback:
                        feedback_callback(f"[+] 成功：{policy_id}")

                except subprocess.CalledProcessError as e:
                    error_msg = f"[-] 策略 {policy_id} 执行失败！Error:\n{e.stderr}"
                    print(error_msg)
                    if feedback_callback:
                        feedback_callback(error_msg)
                    success_all = False
                    failed_at = policy_id
                    break # 发生错误，终止后续规划
                except subprocess.TimeoutExpired:
                    error_msg = f"[-] 策略 {policy_id} 执行超时！"
                    print(error_msg)
                    if feedback_callback:
                        feedback_callback(error_msg)
                    success_all = False
                    failed_at = policy_id
                    break
            else:
                error_msg = f"未知策略ID: {policy_id}"
                print(error_msg)
                if feedback_callback:
                    feedback_callback(error_msg)
                success_all = False
                failed_at = policy_id
                break

        return success_all, failed_at