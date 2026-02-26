# -*- coding: utf-8 -*-
# scripts/tool_get_coords.py

import sys
import os
import time
import cv2
import threading

# 路径处理: 确保能导入上级目录的模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from pymycobot import MyCobot280
    from config import settings 
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保在项目根目录下运行，或检查环境配置。")
    sys.exit(1)

# --- 配置 ---
# 直接使用 settings 中的配置
PORT = settings.PORT
BAUD = settings.BAUD
GPIO_GRIPPER = getattr(settings, 'GPIO_GRIPPER', 2) # 默认引脚 2

def robot_control_thread(mc, state_dict):
    """
    后台线程：专门负责读取机械臂状态，防止阻塞摄像头画面
    """
    while state_dict['running']:
        try:
            # 只有在需要刷新数据时才读取（避免频繁占用串口）
            if state_dict['need_update']:
                coords = mc.get_coords()
                angles = mc.get_angles()
                if coords and angles:
                    state_dict['current_coords'] = coords
                    state_dict['current_angles'] = angles
                state_dict['need_update'] = False 
            
            time.sleep(0.1)
        except Exception as e:
            print(f"读取异常: {e}")

def main():
    print(f"正在连接机械臂 ({PORT})...")
    try:
        mc = MyCobot280(PORT, BAUD)
        time.sleep(0.5)
        mc.power_on()
        print("✅ 机械臂连接成功！")
        
        # 初始状态：松开气爪 (0)
        mc.set_basic_output(GPIO_GRIPPER, 0)
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    # 打开摄像头
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("❌ 无法打开摄像头")
        return

    print("\n" + "="*50)
    print("   🦾 机械臂示教助手 (Robot Teach Tool)   ")
    print("="*50)
    print(" [ R ] -> 解锁 (Release): 手动拖动机械臂")
    print(" [ L ] -> 锁定 (Lock):    保持当前姿态")
    print(" [ O ] -> 松开 (Open):    气爪张开 (信号 0)")
    print(" [ C ] -> 闭合 (Close):   气爪闭合 (信号 1)")
    print(" [ P ] -> 打印 (Print):   获取坐标并打印")
    print(" [ Q ] -> 退出 (Quit)")
    print("="*50 + "\n")

    # 共享状态
    state = {
        'running': True,
        'need_update': True, 
        'current_coords': [],
        'current_angles': [],
        'servo_status': 'Locked',
        'gripper_status': 'Open' # 默认初始状态
    }

    # 启动后台读取线程
    t = threading.Thread(target=robot_control_thread, args=(mc, state))
    t.daemon = True
    t.start()

    window_name = "Robot Teach Tool (Press Q to Quit)"
    cv2.namedWindow(window_name)

    while True:
        ret, frame = cap.read()
        if not ret: break

        # --- UI 显示 ---
        # 1. 舵机状态
        status_color = (0, 255, 0) if state['servo_status']=='Locked' else (0, 0, 255)
        cv2.putText(frame, f"Servo: {state['servo_status']}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        # 2. 气爪状态 (新增)
        gripper_color = (255, 255, 0) if state['gripper_status']=='Open' else (0, 165, 255)
        cv2.putText(frame, f"Gripper: {state['gripper_status']}", (10, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, gripper_color, 2)

        # 3. 坐标显示
        if state['current_coords']:
            # 显示 Angles (角度 - 示教主要用这个)
            # 格式化一下，保留2位小数
            angles_str = ", ".join([f"{x:.2f}" for x in state['current_angles']])
            cv2.putText(frame, f"Angles: [{angles_str}]", (10, 450), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        cv2.imshow(window_name, frame)
        
        key = cv2.waitKey(1) & 0xFF

        # --- 按键逻辑 ---
        
        # 1. 舵机解锁
        if key == ord('r'): 
            mc.release_all_servos()
            state['servo_status'] = 'Released'
            print(">>> 🔓 已解锁，请拖动...")
        
        # 2. 舵机锁定
        elif key == ord('l'): 
            mc.power_on() 
            state['servo_status'] = 'Locked'
            state['need_update'] = True 
            print(">>> 🔒 已锁定！")
        
        # 3. 气爪松开 (Open) - 发送 0
        elif key == ord('o'):
            mc.set_basic_output(GPIO_GRIPPER, 0)
            state['gripper_status'] = 'Open'
            print(">>> 🖐️ 气爪松开 (Signal: 0)")

        # 4. 气爪闭合 (Close) - 发送 1
        elif key == ord('c'):
            mc.set_basic_output(GPIO_GRIPPER, 1)
            state['gripper_status'] = 'Closed'
            print(">>> ✊ 气爪闭合 (Signal: 1)")

        # 5. 打印坐标
        elif key == ord('p'): 
            state['need_update'] = True 
            time.sleep(0.1) # 等待线程更新数据
            
            print("\n" + "-"*30)
            print("📍 [CAPTURE] 当前点位数据:")
            print(f"Coords (坐标): {state['current_coords']}")
            print(f"Angles (角度): {state['current_angles']}")
            print("-"*30 + "\n")
            
            # 屏幕闪烁提示
            cv2.putText(frame, "SAVED!", (250, 240), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)
            cv2.imshow(window_name, frame)
            cv2.waitKey(200)

        elif key == ord('q'):
            break
        
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            break

    state['running'] = False
    cap.release()
    cv2.destroyAllWindows()
    # 退出前松开气爪，确保安全
    try:
        mc.set_basic_output(GPIO_GRIPPER, 0)
    except: pass
    print("程序已退出。")

if __name__ == "__main__":
    main()