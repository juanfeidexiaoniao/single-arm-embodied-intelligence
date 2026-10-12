import os
from openai import OpenAI
import openai
import pyaudio
import wave
import whisper
import threading
import time
import numpy as np
from pynput import keyboard
import re

# ===================== 核心修改1：自动识别蓝牙麦克风设备 =====================
def get_bluetooth_mic_index():
    """自动查找蓝牙麦克风（MR02）的设备索引"""
    audio = pyaudio.PyAudio()
    bluetooth_index = None
    print("=== 可用的输入设备列表 ===")
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            device_name = info['name']
            print(f"索引 {i}: {device_name} | 最大输入声道: {info['maxInputChannels']} | 默认采样率: {info['defaultSampleRate']}")
            # 匹配蓝牙麦克风名称（MR02），可根据实际名称调整关键词
            if "MR02" in device_name or "bluetooth" in device_name.lower() or "handsfree" in device_name.lower():
                bluetooth_index = i
                print(f"✅ 找到蓝牙麦克风，索引：{bluetooth_index}")
    audio.terminate()
    # 如果没找到蓝牙麦克风，使用默认设备（可手动指定索引）
    return bluetooth_index if bluetooth_index is not None else 0

# ===================== 配置参数（适配蓝牙麦克风） =====================
# 核心修改2：适配蓝牙麦克风的参数（16000Hz采样率、单声道）
FORMAT = pyaudio.paInt16  # 音频格式（蓝牙麦克风支持）
CHANNELS = 1  # 单声道（蓝牙麦克风默认）
RATE = 16000  # 蓝牙麦克风采样率（原48000Hz不兼容）
CHUNK = 1024   # 适配蓝牙的块大小（原32768过大）
RECORD_SECONDS = 30  # 录制时长
TEMP_AUDIO_FILE = "temp_audio.wav"  # 临时音频文件
MODEL_NAME = "medium"  # Whisper模型（支持16000Hz）

# 全局变量控制录音状态
kwa = {'end': True}

# 正则表达式（保持不变）
pattern = re.compile(r'python lerobot/scripts/control_robot\.py record \\\n\-\-robot-path lerobot/configs/robot/6DOF_ARM\.yaml \\\n\-\-fps 60 \\\n\-\-tags so100 tutorial eval \\\n\-\-warmup\-time\-s 2 \\\n\-\-episode\-time\-s 100 \\\n\-\-reset\-time\-s 5 \\\n\-\-num\-episodes 2 \\\n\-\-push\-to\-hub 0 \\\n\-\-local\-files\-only 1 \\\n\-\-root 6dof_arm_data\\\n\-\-repo\-id \$\{HF_USER\}/eval_6dof_arm \\\n\-\-\S+ experiment \\\n\-p outputs/train/act_so100_test_2/checkpoints/last/pretrained_model')

# 加载Whisper模型
model = whisper.load_model(MODEL_NAME)

# OpenAI配置（保持不变）
client = OpenAI(
    api_key=os.environ["SPARK_API_KEY"],
    base_url="https://spark-api-open.xf-yun.com/x2",
)
stream_res = False

# ===================== 录音函数（核心修改3：使用蓝牙麦克风） =====================
def record_audio():
    """实时录制蓝牙麦克风音频并保存为临时文件"""
    # 获取蓝牙麦克风索引
    bluetooth_mic_index = get_bluetooth_mic_index()
    if bluetooth_mic_index is None:
        print("❌ 未找到蓝牙麦克风，使用默认设备")
        bluetooth_mic_index = 0

    audio = pyaudio.PyAudio()
    stream = None
    wf = None
    try:
        # 核心修改4：打开蓝牙麦克风音频流
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=bluetooth_mic_index,  # 使用蓝牙麦克风索引
            frames_per_buffer=CHUNK
        )
        
        print("\n🎤 开始录音（按空格键暂停/继续，ESC退出）...")
        frames = []
        
        # 录制音频（支持实时停止）
        while not kwa['end']:
            data = stream.read(CHUNK, exception_on_overflow=False)  # 防止缓冲区溢出
            frames.append(data)
        
        # 保存音频文件
        wf = wave.open(TEMP_AUDIO_FILE, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        print(f"✅ 录音完成，已保存到 {TEMP_AUDIO_FILE}")

    except Exception as e:
        print(f"❌ 录音出错: {e}")
    finally:
        # 核心修改5：安全释放资源（修复原代码冗余逻辑）
        if stream:
            stream.stop_stream()
            stream.close()
        if audio:
            audio.terminate()
        if wf:
            wf.close()

    # 转录音频
    transcribe_audio()

# ===================== 其他函数（保持不变） =====================
def transmit_data_to_AI(texts):
    stream_a = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": f"aaa{texts}aaa，分析我提供的、被两个`aaa`包裹的文本，如果有“苹果”这两个字或者相近意思的词，就返回给我“python lerobot/scripts/control_robot.py record \\\n\
--robot-path lerobot/configs/robot/6DOF_ARM.yaml \\\n\
--fps 60 \\\n\
--tags so100 tutorial eval \\\n\
--warmup-time-s 2 \\\n\
--episode-time-s 100 \\\n\
--reset-time-s 5 \\\n\
--num-episodes 2 \\\n\
--push-to-hub 0 \\\n\
--local-files-only 1 \\\n\
--root 6dof_arm_data\\\n\
--repo-id ${HF_USER}/eval_6dof_arm \\\n\
--single-task experiment \\\n\
-p outputs/train/act_so100_test_2/checkpoints/last/pretrained_model”这段话，否则返回“aaabbbcccddd”这段话"
            }
        ],
        model="spark-x",
        stream=stream_res,
        user="robot-user",
    )
    print('\n——————————————————————————————————————————\n'+stream_a.choices[0].message.content+'\n——————————————————————————————————————————\n')
    we_re = pattern.search(stream_a.choices[0].message.content)
    we_string = we_re.group() if we_re else 'aaabbbcccddd'
    if we_string != 'aaabbbcccddd':
        os.system(we_string)
    else:
        print('\n抱歉，未能识别您的指令')

def transcribe_audio():
    """使用Whisper转录音频"""
    time.sleep(0.1)
    if os.path.exists(TEMP_AUDIO_FILE):
        try:
            # Whisper自动适配16000Hz采样率
            result = model.transcribe(TEMP_AUDIO_FILE, language="zh", fp16=False)
            text = result["text"].strip()
            print(f"\n📝 转录结果: {text}")
            # 异步调用AI
            transmit_thread = threading.Thread(target=transmit_data_to_AI, args=(text,), daemon=True)
            transmit_thread.start()
        except Exception as e:
            print(f"❌ 转录出错: {e}")

def keyboard_listener(key):
    """键盘监听：空格键开始/暂停录音，ESC退出"""
    global kwa
    if key == keyboard.Key.space:
        kwa['end'] = not kwa['end']
        if not kwa['end']:
            # 启动录音线程
            speech_thread = threading.Thread(target=record_audio, daemon=True)
            speech_thread.start()
    elif key == keyboard.Key.esc:
        kwa['end'] = True
        print("\n👋 退出程序")
        return False

def main():
    print("=== 蓝牙麦克风语音识别程序 ===")
    print("操作说明：按空格键开始/暂停录音，按ESC退出")
    with keyboard.Listener(on_press=keyboard_listener) as listener:
        listener.join()

if __name__ == "__main__":
    main()
