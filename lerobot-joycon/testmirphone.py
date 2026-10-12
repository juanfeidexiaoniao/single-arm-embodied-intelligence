import pyaudio

# 初始化PyAudio
p = pyaudio.PyAudio()

# 遍历并打印所有音频设备
print("===== 所有音频设备列表 =====")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    # 只打印输入设备（可选，去掉if就是全部设备）
    if info["maxInputChannels"] > 0:
        print(f"设备索引: {info['index']}")
        print(f"设备名称: {info['name']}")
        print(f"输入通道数: {info['maxInputChannels']}")
        print("-" * 40)

p.terminate()