# scripts/tool_get_coords.py
import sys
import os
import time
import cv2
import threading

# 路径处理
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from pymycobot import MyCobot280
    from config import settings  # 尝试导入配置文件读取端口，如果没有则使用默认
except ImportError:
    print("⚠️ 警告：无法导入 config 或 pymycobot，将使用默认设置")

# --- 配置 ---
# 如果 settings.py 里没有 PORT，请手动修改这里
PORT = getattr(settings, 'PORT', "COM3") 
BAUD = 115200

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
                state_dict['need_update'] = False # 读完一次就休息，等待下次指令
            
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
    print(" [ R ] -> 解锁/放松 (Release): 手动拖动机械臂")
    print(" [ L ] -> 锁定/固定 (Lock):    保持当前姿态")
    print(" [ P ] -> 打印坐标 (Print):    获取当前位置数据")
    print(" [ Q ] -> 退出程序")
    print("="*50 + "\n")

    # 共享状态
    state = {
        'running': True,
        'need_update': True, # 初始读取一次
        'current_coords': [],
        'current_angles': [],
        'servo_status': 'Locked' # 默认为锁定状态
    }

    # 启动后台线程读取数据（为了不让画面卡顿）
    t = threading.Thread(target=robot_control_thread, args=(mc, state))
    t.daemon = True
    t.start()

    window_name = "Robot Teach Tool"
    cv2.namedWindow(window_name)

    while True:
        ret, frame = cap.read()
        if not ret: break

        # 在画面上显示当前状态
        cv2.putText(frame, f"Status: {state['servo_status']}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0) if state['servo_status']=='Locked' else (0, 0, 255), 2)
        
        # 显示最近一次读取的坐标
        if state['current_coords']:
            # 显示 XYZ
            xyz_str = f"XYZ: [{state['current_coords'][0]:.1f}, {state['current_coords'][1]:.1f}, {state['current_coords'][2]:.1f}]"
            cv2.putText(frame, xyz_str, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            # 显示 Rz (末端旋转)
            if len(state['current_coords']) > 5:
                rz_str = f"Rz: {state['current_coords'][5]:.1f}"
                cv2.putText(frame, rz_str, (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        cv2.imshow(window_name, frame)
        
        key = cv2.waitKey(1) & 0xFF

        # --- 按键逻辑 ---
        
        if key == ord('r'): # Release (放松)
            mc.release_all_servos()
            state['servo_status'] = 'Released (Manual Mode)'
            print(">>> 🔓 机械臂已解锁，请手动拖动...")
        
        elif key == ord('l'): # Lock (锁定)
            mc.power_on() # power_on 会重新上电锁定舵机
            state['servo_status'] = 'Locked (Hold Position)'
            print(">>> 🔒 机械臂已锁定！")
            # 锁定后立即刷新一次数据
            state['need_update'] = True 
        
        elif key == ord('p'): # Print (打印)
            state['need_update'] = True # 触发后台线程读取
            # 稍微延时一下等待读取完成（简单粗暴）
            time.sleep(0.1) 
            
            print("\n" + "-"*30)
            print("📍 当前位置捕获:")
            print(f"   Coords (坐标): {state['current_coords']}")
            print(f"   Angles (角度): {state['current_angles']}")
            print("-"*30 + "\n")
            
            # 可以在这里做个闪光效果提示截图成功
            cv2.putText(frame, "Captured!", (320, 240), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 255), 3)
            cv2.imshow(window_name, frame)
            cv2.waitKey(200)

        elif key == ord('q'): # Quit
            break
        
        # 窗口关闭检测
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            break

    state['running'] = False
    cap.release()
    cv2.destroyAllWindows()
    print("程序已退出。")

if __name__ == "__main__":
    main()