import os, openai, pyaudio, wave, whisper, threading, time, cv2, base64, subprocess, csv
from openai import OpenAI
import numpy as np
from pynput import keyboard

p = pyaudio.PyAudio()
# 1. 定义你的 CSV 文件路径
csv_file = "jinengku.csv"  # 替换成你的文件路径

# 2. 创建空字典用于存储结果
result_dict = {}

# 3. 读取并生成字典
with open(csv_file, mode='r', encoding='utf-8') as file:
    # 读取每一行（不把第一行当作表头，直接读取）
    csv_reader = csv.reader(file)
    
    for row in csv_reader:
        # 确保每行至少有两列，避免报错
        if len(row) >= 2:
            key = row[0]       # 第一列 = 键
            value = row[1]     # 第二列 = 值
            result_dict[key] = value

# 4. 输出结果
can_action = result_dict
print("Available input devices:")
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

# 全局变量控制录音状态
kwa = {'end' : True}

# 加载Whisper模型
model = whisper.load_model(MODEL_NAME)

client = OpenAI(
   
    api_key=os.environ["SPARK_API_KEY"], # 两种方式：1、http协议的APIpassword； 2、ws协议的apikey和apisecret 按照ak:sk格式拼接；
    base_url="https://spark-api-open.xf-yun.com/x2",
)

# stream_res = True
stream_res = False

def camera_capture(index_list):
    phone_list = []
    for i in index_list:
        cap = cv2.VideoCapture(i)
        if not cap.isOpened():
            print("Error: Could not open camera"+str(i))
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

        model="spark-x",
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
    
    print("开始实时语音转文字（按Ctrl+C停止）...\n")
    frames = []
   
    # 录制指定时长的音频
    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)
        if kwa['end']:
            break

    kwa['end'] = True
   
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
   
    # 删除临时文件
    if os.path.exists(TEMP_AUDIO_FILE):
       os.remove(TEMP_AUDIO_FILE)

def transmit_data_to_AI(texts):
    stream_a = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": f"场景信息:{scene}\n\
                    可用动作：{list(can_action.keys())}\n\
                    目的：{texts}\n\
                    返回形式：[action_id1, action_id2, action_id3]\n\
                        text：请根据我所提供的场景信息，从机械臂可用的动作中选择一个或多个动作并排列顺序来达到目的，若能达到目的返回的结果必须是规定的返回形式。注：每个动作都是从机械臂归零状态开始，以归零状态结束，若我提供的动作无论如何搭配都不能达到目的，请返回“抱歉，我无法完成这个要求”，若我提供的目的十分不明确，请返回“抱歉，我没有听懂您的要求”"
            },

        ],

        model="spark-x",
        stream=stream_res,
        user="robot-user",

    )
    print('\n——————————————————————————————————————————\n'+stream_a.choices[0].message.content+'\n——————————————————————————————————————————\n')
    val = stream_a.choices[0].message.content
    if val[0] == '[' and val[-1] == ']':
        for a in val[1: -1].split(','):
            st = 'python lerobot/scripts/control_robot.py record \\\n\
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
  --single-task '+can_action[a]+' \\\n\
  -p outputs/train/act_'+can_action[a]+'/checkpoints/last/pretrained_model'
            try:
                # 在 Linux  shell 中执行命令
                subprocess.run(
                    a,
                    shell=True,
                    check=True,
                    stdout=None,  # 直接输出到终端
                    stderr=None
                )

            except subprocess.CalledProcessError:
                print("命令执行失败！")
        global scene
        scene = camera_capture([2, 4, 6])
    else:
        print(val)

def transcribe_audio():
    """
    实时转录音频文件
    """
    # 等待音频文件生成
    time.sleep(0.1)
    if os.path.exists(TEMP_AUDIO_FILE):
        try:
            # 使用Whisper转录
            result = model.transcribe(TEMP_AUDIO_FILE, language="zh", fp16=False)
            text = result["text"].strip()
           
            # 输出转录结果
            print(text, end='')
           
            transmit_thread = threading.Thread(target=transmit_data_to_AI, args=(text, ), daemon=True)
            transmit_thread.start()
        except Exception as e:
            print(f"转录出错: {e}")

def keyboard_listener(key):
    if key == keyboard.Key.space:
        kwa['end'] = not kwa['end']
        if not kwa['end']:
            speech_to_text_thread = threading.Thread(target=record_audio, daemon=True)
            speech_to_text_thread.start()
    elif key == keyboard.Key.esc:
        return False

def main():
    global scene
    scene = camera_capture([2, 4, 6])
    with keyboard.Listener(on_press=keyboard_listener) as listener:
        listener.join()

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