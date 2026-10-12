import pygame
import sys
import time

def test_joycon_connection():
    # 初始化 pygame
    pygame.init()
    
    # 初始化手柄模块
    pygame.joystick.init()
    
    # 检测连接的手柄数量
    joystick_count = pygame.joystick.get_count()
    print(f"检测到 {joystick_count} 个游戏手柄/控制器")
    
    if joystick_count == 0:
        print("未检测到任何游戏手柄或 Joy-Con。请确保设备已连接。")
        return
    
    # 遍历所有检测到的手柄
    for i in range(joystick_count):
        joystick = pygame.joystick.Joystick(i)
        joystick.init()
        
        print(f"\n--- 手柄 {i} ---")
        print(f"名称: {joystick.get_name()}")
        print(f"轴数量: {joystick.get_numaxes()}")
        print(f"按钮数量: {joystick.get_numbuttons()}")
        print(f"帽子开关数量: {joystick.get_numhats()}")
        
        # 识别 Joy-Con
        name = joystick.get_name().lower()
        if "joy-con" in name or "nintendo" in name:
            print("检测到 Joy-Con 控制器!")
            if "left" in name:
                print("类型: Joy-Con (左)")
            elif "right" in name:
                print("类型: Joy-Con (右)")
            else:
                print("类型: 未知 Joy-Con")
        else:
            print("可能是其他类型的手柄")
    
    # 开始测试输入
    print("\n--- 开始测试输入 ---")
    print("按下 Joy-Con 上的按钮，查看输入响应")
    print("左摇杆: 移动轴")
    print("右摇杆: 移动轴")
    print("按下 L3/R3: 按钮")
    print("按 Ctrl+C 退出测试")
    
    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                
                # 处理按钮按下事件
                if event.type == pygame.JOYBUTTONDOWN:
                    print(f"手柄 {event.joy} 按钮 {event.button} 按下")
                
                # 处理按钮释放事件
                if event.type == pygame.JOYBUTTONUP:
                    print(f"手柄 {event.joy} 按钮 {event.button} 释放")
                
                # 处理轴移动事件
                if event.type == pygame.JOYAXISMOTION:
                    # 只显示有实际移动的轴事件（绝对值 > 0.1）
                    if abs(event.value) > 0.1:
                        print(f"手柄 {event.joy} 轴 {event.axis} 移动: {event.value:.2f}")
                
                # 处理帽子开关事件
                if event.type == pygame.JOYHATMOTION:
                    print(f"手柄 {event.joy} 帽子开关 {event.hat} 移动: {event.value}")
            
            time.sleep(0.01)  # 减少 CPU 使用率
            
    except KeyboardInterrupt:
        print("\n测试结束")
    
    # 退出 pygame
    pygame.quit()

if __name__ == "__main__":
    test_joycon_connection()
