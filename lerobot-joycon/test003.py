import os
# 强制 sounddevice 使用 PortAudio 的 PulseAudio 后端（必须放在最前面）
os.environ['PA_ALSA_PLUGHW'] = '0'
os.environ['PA_ALSA_USE_DEFAULT'] = '0'
os.environ['PA_ALSA_DEVICE'] = 'pulse'

from openai import OpenAI
import whisper
import threading
import time
import re
import sounddevice as sd
import soundfile as sf
from pynput import keyboard
import numpy as np
from scipy import signal

# ===================== 核心配置 =====================
WHISPER_SAMPLERATE = 16000  # Whisper要求的采样率
CHANNELS = 1                 # 单声道
TEMP_AUDIO_FILE = "temp_audio.wav"
MODEL_NAME = "medium"

# 全局变量
recording = False
audio_data = []
kwa = {'end': True}

# 正则表达式（保持不变）
pattern = re.compile(r'python lerobot/scripts/control_robot\.py record \\\n\-\-robot-path lerobot/configs/robot/6DOF_ARM\.yaml \\\n\-\-fps 60 \\\n\-\-tags so100 tutorial eval \\\n\-\-warmup\-time\-s 2 \\\n\-\-episode\-time\-s 100 \\\n\-\-reset\-time\-s 5 \\\n\-\-num\-episodes 2 \\\n\-\-push\-to\-hub 0 \\\n\-\-local\-files\-only 1 \\\n\--root 6dof_arm_data\\\n\-\-repo\-id \$\{HF_USER\}/eval_6dof_arm \\\n\-\-\S+ experiment \\\n\-p outputs/train/act_so100_test_2/checkpoints/last/pretrained_model')

# 加载Whisper模型
model = whisper.load_model(MODEL_NAME)

# OpenAI配置
client = OpenAI(
    api_key=os.environ["SPARK_API_KEY"],
    base_url="https://spark-api-open.xf-yun.com/x2",
)
stream_res = False

# ===================== 核心工具函数 =====================
def get_bluetooth_device():
    """自动查找并返回蓝牙麦克风的设备索引和支持的采样率"""
    devices = sd.query_devices()
    print("\n=== 所有可用输入设备 ===")
    bluetooth_idx = None
    supported_samplerates = []
    
    for idx, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            print(f"索引 {idx}: {dev['name']} | 声道: {dev['max_input_channels']} | 默认采样率: {dev['default_samplerate']}")
            # 匹配蓝牙设备关键词（可根据实际名称调整）
            if any(keyword in dev['name'].lower() for keyword in ['mr02', 'bluetooth', 'handsfree', 'bluez', 'headset', 'wireless']):

                bluetooth_idx = idx
                # 获取设备支持的采样率（尝试常见值）
                for sr in [48000, 44100, 32000, 22050, 16000]:
                    try:
                        sd.check_input_settings(samplerate=sr, channels=CHANNELS, device=bluetooth_idx)
                        supported_samplerates.append(sr)
                    except:
                        pass
                print(f"✅ 找到蓝牙麦克风！索引: {bluetooth_idx} | 支持的采样率: {supported_samplerates}")
    
    # 如果没找到蓝牙设备，使用默认设备
    if bluetooth_idx is None:
        print("⚠️  未找到蓝牙麦克风，使用默认输入设备")
        bluetooth_idx = sd.default.device[0]
        supported_samplerates = [int(devices[bluetooth_idx]['default_samplerate'])]
    
    # 选择最接近Whisper要求的采样率（优先选高的，重采样后音质更好）
    best_sr = min(supported_samplerates, key=lambda x: abs(x - WHISPER_SAMPLERATE))
    return bluetooth_idx, best_sr

def resample_audio(audio_np, original_sr, target_sr):
    """重采样音频到目标采样率（供Whisper使用）"""
    if original_sr == target_sr:
        return audio_np
    # 计算重采样比例
    ratio = target_sr / original_sr
    # 重采样
    resampled = signal.resample(audio_np, int(len(audio_np) * ratio))
    return resampled.astype(np.int16)

# ===================== 录音函数 =====================
def callback(indata, frames, time, status):
    if status:
        print(f"⚠️  录音状态: {status}", flush=True)
    if recording:
        audio_data.append(indata.copy())

def record_audio():
    global recording, audio_data
    audio_data = []
    recording = True
    
    try:
        # 获取蓝牙设备和最佳采样率
        bluetooth_idx, device_sr = get_bluetooth_device()
        print(f"\n🎤 使用设备索引 {bluetooth_idx}，采样率 {device_sr}Hz 开始录音...")
        print("（按空格键停止，ESC退出）")
        
        # 打开音频流
        with sd.InputStream(
            samplerate=device_sr,
            channels=CHANNELS,
            callback=callback,
            device=bluetooth_idx,
            dtype='int16'
        ):
            while recording and not kwa['end']:
                time.sleep(0.1)
        
        # 处理录音数据
        if audio_data:
            audio_np = np.concatenate(audio_data, axis=0)
            # 重采样到Whisper要求的16000Hz
            if device_sr != WHISPER_SAMPLERATE:
                print(f"🔄 重采样音频: {device_sr}Hz → {WHISPER_SAMPLERATE}Hz")
                audio_np = resample_audio(audio_np.flatten(), device_sr, WHISPER_SAMPLERATE).reshape(-1, 1)
            # 保存音频文件
            sf.write(TEMP_AUDIO_FILE, audio_np, WHISPER_SAMPLERATE)
            print(f"✅ 录音完成，已保存到 {TEMP_AUDIO_FILE}")
            transcribe_audio()
        else:
            print("⚠️  未录制到音频数据")
    
    except Exception as e:
        print(f"❌ 录音出错: {e}")
    finally:
        recording = False
        kwa['end'] = True

# ===================== 其他函数 =====================
def transmit_data_to_AI(texts):
    try:
        stream_a = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": "aaa{texts}aaa，分析我提供的、被两个`aaa`包裹的文本，如果有“苹果”这两个字或者相近意思的词，就返回给我“python lerobot/scripts/control_robot.py record \\\n\
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
    except Exception as e:
        print(f"❌ AI调用出错: {e}")

def transcribe_audio():
    if os.path.exists(TEMP_AUDIO_FILE):
        try:
            result = model.transcribe(TEMP_AUDIO_FILE, language="zh", fp16=False)
            text = result["text"].strip()
            print(f"\n📝 转录结果: {text}")
            transmit_thread = threading.Thread(target=transmit_data_to_AI, args=(text,), daemon=True)
            transmit_thread.start()
        except Exception as e:
            print(f"❌ 转录出错: {e}")

def keyboard_listener(key):
    global recording, kwa
    if key == keyboard.Key.space:
        if not kwa['end']:
            recording = False
            kwa['end'] = True
            print("\n⏹️  停止录音")
        else:
            kwa['end'] = False
            record_thread = threading.Thread(target=record_audio, daemon=True)
            record_thread.start()
    elif key == keyboard.Key.esc:
        recording = False
        kwa['end'] = True
        print("\n👋 退出程序")
        return False

def main():
    # 强制使用系统音频库
    os.environ['LD_LIBRARY_PATH'] = '/usr/lib/x86_64-linux-gnu:' + os.environ.get('LD_LIBRARY_PATH', '')
    
    print("=== 蓝牙麦克风语音识别程序（最终版） ===")
    print("操作说明：按空格键开始/停止录音，按ESC退出")
    with keyboard.Listener(on_press=keyboard_listener) as listener:
        listener.join()

if __name__ == "__main__":
    main()
