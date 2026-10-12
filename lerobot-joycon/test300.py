import os, openai, pyaudio, wave, whisper, threading, time, cv2, base64, subprocess, csv, re
from openai import OpenAI
import numpy as np
from pynput import keyboard
import tkinter as tk
from tkinter import ttk

# 全局退出事件：用于安全通知所有线程停止运行
exit_event = threading.Event()
# 存储Tkinter窗口对象，方便跨线程关闭
tk_window = None

p = pyaudio.PyAudio()
# 1. 定义你的 CSV 文件路径
csv_file = "jinengku.csv"  # 替换成你的文件路径

pattern = re.compile(r'\[.+\]')

# 2. 创建空字典用于存储结果
result_dict = {}

# 3. 读取并生成字典
with open(csv_file, mode='r', encoding='utf-8') as file:
    # 读取每一行（不把第一行当作表头，直接读取）
    csv_reader = csv.reader(file)
    n = True
    
    for row in csv_reader:
        # 确保每行至少有两列，避免报错
        if len(row) >= 2:
            if n:
                key = row[0][1:]
                n = False
            else:
                key = row[0]       # 第一列 = 键
            value = row[1]     # 第二列 = 值
            result_dict[key] = value
del n
# 4. 输出结果
can_action = result_dict
action_id_list = list(can_action.keys())
#print("Available input devices:")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f"Index {i}: {info['name']} - maxInputChannels={info['maxInputChannels']}, defaultSampleRate={info['defaultSampleRate']}")
p.terminate()
# 配置参数
FORMAT = pyaudio.paInt16  # 音频格式
CHANNELS = 1  # 单声道
RATE = 16000  # 采样率（Whisper推荐16000Hz）
CHUNK = 4096   # 每次读取的音频块大小
RECORD_SECONDS = 30  # 每次录制的分片时长（秒）
TEMP_AUDIO_FILE = "temp_audio.wav"  # 临时音频文件
MODEL_NAME = "medium"  # Whisper模型大小（tiny/base/small/medium/large）

# 加载Whisper模型
model = whisper.load_model(MODEL_NAME)

client = OpenAI(
   
    api_key=os.environ["DASHSCOPE_API_KEY"], # 两种方式：1、http协议的APIpassword； 2、ws协议的apikey和apisecret 按照ak:sk格式拼接；
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# stream_res = True
stream_res = False

camera_index = [6]

def camera_capture(index_list):
    phone_list = []
    for i in index_list:
        cap = cv2.VideoCapture(i)
        if not cap.isOpened():
            app.text.insert(tk.END, f"Error: Could not open camera{str(i)}\n\n")
            app.text.see(tk.END)
            cap.release()
            cv2.destroyAllWindows()
            return
        for _ in range(5):
            ret, frame = cap.read()
        ret, frame = cap.read()
        cv2.imwrite(os.path.join('photo', 'cap'+str(i)+'.jpg'), frame)
        with open(os.path.join('photo', 'cap'+str(i)+'.jpg'), "rb") as f:
            phone_list.append(base64.b64encode(f.read()).decode("utf-8"))
        cap.release()
    stream_a = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": f"phone:{phone_list}\n\
                    text:这是一组从不同角度拍摄的图片，请详细描述图片中的场景，包括所有物体及其相对位置。"
            },

        ],

        model="qwen2.5-vl-72b-instruct",
        stream=stream_res,
        user="robot-user",

    )
    cv2.destroyAllWindows()
    return stream_a.choices[0].message.content

def record_audio():
    """
    实时录制音频并保存为临时文件
    """
    audio = pyaudio.PyAudio()
    # 打开音频流
    stream = audio.open(format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=2,
        frames_per_buffer=CHUNK)
    
    app.text.insert(tk.END, f"开始实时语音转文字...\n\n")
    app.text.see(tk.END)
    frames = []
   
    # 录制指定时长的音频
    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)
        if not app.is_locked:
            break

    # 保存临时音频文件
    wf = wave.open(TEMP_AUDIO_FILE, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(audio.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
   
    # 停止录音
    stream.stop_stream()
    stream.close()
    audio.terminate()
    wf.close()

    '''try:
        if stream is not None:
            if stream.is_active():
                stream.stop_stream()
            stream.close()
            stream = None

        if audio is not None:
            audio.terminate()
            audio = None

        if wf is not None:
            wf.close()
            wf = None

    except Exception as e:
        pass'''

    transcribe_audio()

    app.is_locked = True
    app.toggle_entry()
    app.text.insert(tk.END, f"实时语音转文字已结束\n\n")
    app.text.see(tk.END)
   
    # 删除临时文件
    if os.path.exists(TEMP_AUDIO_FILE):
       os.remove(TEMP_AUDIO_FILE)

def transmit_data_to_AI(texts):
    global scene
    stream_a = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": f"场景信息:{scene}\n\
                    可用动作：{list(can_action.keys())}\n\
                    目的：{texts}\n\
                    text：请根据我所提供的场景信息，从机械臂可用的动作中选择一个或多个动作并排列顺序来达到目的，若能达到目的，返回的结果必须是规定的返回形式，总的来说，返回的文本中只能出现一个'['与一个']'。注：每个动作都是从机械臂归零状态开始，以归零状态结束，若我提供的动作无论如何搭配都不能达到目的，请返回“抱歉，我无法完成这个要求”，若我提供的目的十分不明确，请返回“抱歉，我没有听懂您的要求”；action_id从1开始而不是0\n\
                    返回形式：[action_id1, action_id2, action_id3]"
            }           
        ],

        model="qwen2.5-vl-72b-instruct",
        stream=stream_res,
        user="robot-user",

    )
    app.text.insert(tk.END, f"模型返回：{stream_a.choices[0].message.content}\n\n")
    app.text.see(tk.END)
    val = pattern.search(stream_a.choices[0].message.content)
    if val != None:
        val = val.group()
        for a in val[1: -1].split(','):
            try:
                a = action_id_list[int(a)-1]
            except ValueError:
                pass
            st = 'python lerobot/scripts/control_robot.py record \\\n\
  --robot-path lerobot/configs/robot/6DOF_ARM.yaml \\\n\
  --fps 60 \\\n\
  --tags so100 tutorial eval \\\n\
  --warmup-time-s 2 \\\n\
  --episode-time-s 20 \\\n\
  --reset-time-s 5 \\\n\
  --num-episodes 1 \\\n\
  --push-to-hub 0 \\\n\
  --local-files-only 1 \\\n\
  --root 6dof_arm_data\\\n\
  --repo-id ${HF_USER}/eval_6dof_arm \\\n\
  --single-task '+can_action[a]+' \\\n\
  -p outputs/train/'+can_action[a]+'/checkpoints/last/pretrained_model'
            app.text.insert(tk.END, f"正在运行：{st}\n\n")
            app.text.see(tk.END)
            try:
                # 在 Linux  shell 中执行命令
                subprocess.run(
                    st,
                    shell=True,
                    check=True,
                    stdout=None,  # 直接输出到终端
                    stderr=None
                )

            except subprocess.CalledProcessError:
                app.text.insert(tk.END, f"命令执行失败\n\n")
                app.text.see(tk.END)
    else:
        pass

def transcribe_audio():
    """
    实时转录音频文件
    """
    # 等待音频文件生成
    while not os.path.exists(TEMP_AUDIO_FILE):
        pass
    try:
        # 使用Whisper转录
        result = model.transcribe(TEMP_AUDIO_FILE, language="zh", fp16=False)
        text = result["text"].strip()
        
        # 输出转录结果
        app.entry_var.set(text)
        
    except Exception as e:
        app.text.insert(tk.END, f"转录出错\n\n")
        app.text.see(tk.END)

def keyboard_listener(key):
    global scene
    try:
        # 检测是否按下了's'键
        if key == keyboard.KeyCode(char='*'):
            if not app.sentai_scene:
                app.send_to_ai_scene()
        elif key == keyboard.KeyCode(char='-'):
            if not app.sentai:
                app.send_to_ai()
        elif key == keyboard.KeyCode(char='+'):
            app.toggle_entry()
    except AttributeError:
        # 处理特殊按键（如Esc、F1等）
        pass
    if key == keyboard.Key.esc:
        if tk_window:
            tk_window.after(0, tk_window.destroy)
        exit_event.set()  # 触发退出事件
        return False

def main():
    global scene
    scene = camera_capture(camera_index)
    app_thread = threading.Thread(target=app_th, daemon=True)
    app_thread.start()
    with keyboard.Listener(on_press=keyboard_listener) as listener:
        while not exit_event.is_set():
            pass
        listener.stop()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.sentai = False
        self.sentai_scene = False
        self.title("Console")
        self.geometry("800x600")
        
        # 1. Entry 绑定的 StringVar
        self.entry_var = tk.StringVar(value="按+开始录音")
        self.is_locked = False  # 控制Entry是否可输入
        
        # --- 布局组件 ---
        # 1. Entry (顶部)
        self.entry = tk.Entry(self, textvariable=self.entry_var, font=("微软雅黑", 12))
        self.entry.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        
        # 2. Button "开/关"
        self.btn_toggle = tk.Button(self, text="打开语音(+)", command=self.toggle_entry, font=("微软雅黑", 12), width=8)
        self.btn_toggle.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        
        # 3. Button "追加文本"
        self.btn_ai_scene = tk.Button(self, text="环境检测(*)", command=self.send_to_ai_scene, font=("微软雅黑", 12), width=8)
        self.btn_ai_scene.grid(row=1, column=1, padx=10, pady=10, sticky="e")

        self.btn_ai = tk.Button(self, text="发送要求(-)", font=("微软雅黑", 12), width=15, command=self.send_to_ai)
        # 放在两个按钮正下方，跨两列居中
        self.btn_ai.grid(row=2, column=0, columnspan=2, padx=10, pady=10)
        
        # 4. Text + Scrollbar (右侧大区域)
        self.text_frame = tk.Frame(self)
        self.text_frame.grid(row=0, column=2, rowspan=2, padx=10, pady=10, sticky="nsew")
        
        self.text = tk.Text(self.text_frame, wrap=tk.WORD, font=("微软雅黑", 12))
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 滚动条
        self.scrollbar = ttk.Scrollbar(self.text_frame, command=self.text.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.config(yscrollcommand=self.scrollbar.set)
        
        # 布局权重分配
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 绑定窗口关闭按钮
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def toggle_entry(self):
        """切换Entry的输入状态和按钮文字"""
        if self.is_locked:
            # 当前是"关" → 切换为"开"，允许输入
            self.btn_toggle.config(text="打开语音(+)")
            self.entry.config(state=tk.NORMAL)
            self.is_locked = False
        else:
            # 当前是"开" → 切换为"关"，禁止输入
            speech_to_text_thread = threading.Thread(target=record_audio, daemon=True)
            speech_to_text_thread.start()
            self.btn_toggle.config(text="关闭语音(+)")
            self.entry.config(state=tk.DISABLED)
            self.is_locked = True

    # -------------------------- 核心功能：发送到大模型 --------------------------
    def send_to_ai(self):
        """点击按钮 → 禁用 → 发请求 → 接收结果 → 解禁"""
        # 1. 禁用按钮
        self.sentai = True
        self.btn_ai.config(state=tk.DISABLED, text="请求中...")
        self.text.insert(tk.END, "\n==== 正在请求大模型，请稍等... ====\n")
        self.text.see(tk.END)

        # 2. 用子线程发请求（防止界面卡住）
        thread = threading.Thread(target=self.request_ai_api)
        thread.start()

    def request_ai_api(self):
        transmit_data_to_AI(self.entry_var.get())

        # 3. 收到结果后，更新界面 + 解禁按钮
        self.after(0, self.update_ui_after_request)

    def update_ui_after_request(self):
        """更新界面 + 解禁按钮"""

        # 解禁按钮
        self.sentai = False
        self.btn_ai.config(state=tk.NORMAL, text="发送要求(-)")

    def send_to_ai_scene(self):
        """点击按钮 → 禁用 → 发请求 → 接收结果 → 解禁"""
        # 1. 禁用按钮
        self.sentai_scene = True
        self.btn_ai_scene.config(state=tk.DISABLED, text="请求中...")
        self.text.insert(tk.END, "\n==== 正在识别环境，请稍等... ====\n")
        self.text.see(tk.END)

        # 2. 用子线程发请求（防止界面卡住）
        thread = threading.Thread(target=self.request_ai_api_scene)
        thread.start()

    def request_ai_api_scene(self):
        global scene
        scene = camera_capture(camera_index)

        # 3. 收到结果后，更新界面 + 解禁按钮
        self.after(0, self.update_ui_after_request_scene)

    def update_ui_after_request_scene(self):
        """更新界面 + 解禁按钮"""

        # 解禁按钮
        self.sentai_scene = False
        self.btn_ai.config(state=tk.NORMAL, text="环境检测(*)")

    def on_window_close(self):
        exit_event.set()  # 通知主线程停止键盘监听
        self.destroy()    # 销毁窗口

def app_th():
    global app
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()


'''stream = client.chat.completions.create(
    messages=[
          {
            "role": "user",
            "content": "你好"
        },

    ],

    model="spark-x",
    stream=stream_res,
    user="123456",

)
full_response = ""

if not stream_res:
    print(stream.to_json())
else:
    for chunk in stream:
        if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content is not None:
            reasoning_content = chunk.choices[0].delta.reasoning_content
            print(reasoning_content, end="", flush=True)  # 实时打印思考模型输出的思考过程每个片段
       
        if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content is not None:
            content = chunk.choices[0].delta.content
            print(content, end="", flush=True)  # 实时打印每个片段
            full_response += content
   
    print("\n\n ------完整响应：", full_response)   '''