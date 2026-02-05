import cv2
import time
import threading
import sys
import os
import webbrowser

from modules.vision import VisionSystem
from modules.arm_control import ArmController
from modules.ai_decision import AIDecisionMaker
from modules import web_server
from config import settings

if settings.SIMULATION_MODE:
    from modules.mock_hardware import MockCamera
else:
    MockCamera = None

class SystemState:
    def __init__(self):
        # 库存
        self.inventory = {i: 0 for i in range(1, 7)}
        # 模式
        self.mode = "IDLE" 
        # 待处理指令 (修复了名字)
        self.pending_ai_cmd = None 
        # 心跳时间戳 (用于检测浏览器是否关闭)
        # 初始化为当前时间 + 15秒 (给浏览器启动留出15秒缓冲时间)
        self.last_heartbeat = time.time() + 15.0 

state = SystemState()

def perform_pick_and_place(arm, target_slot):
    previous_mode = state.mode
    state.mode = "EXECUTING"
    try:
        arm.pick()
        arm.place(target_slot)
        state.inventory[target_slot] = 1
        print(f"✅ [System] {target_slot}号位 已满")
    except Exception as e:
        print(f"❌ [System] 执行出错: {e}")
        arm.go_observe()
    finally:
        if previous_mode == "AUTO":
            state.mode = "AUTO"
        else:
            state.mode = "IDLE"

def get_first_empty_slot():
    for i in range(1, 7):
        if state.inventory[i] == 0:
            return i
    return None

def main():
    arm = ArmController()
    vision = VisionSystem()
    ai = AIDecisionMaker()
    
    if settings.SIMULATION_MODE:
        print("📷 [Main] 使用虚拟摄像头")
        cap = MockCamera()
    else:
        print("📷 [Main] 尝试连接真实摄像头...")
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if arm.mc:
        arm.go_observe()

    # 1. 启动 Web 服务器
    web_thread = threading.Thread(target=web_server.start_flask, args=(state, ai), daemon=True)
    web_thread.start()

    # 2. 自动打开浏览器
    print(">>> 🌐 正在打开 Web 控制台...")
    time.sleep(1.0)
    webbrowser.open("http://127.0.0.1:5000")

    print("\n" + "="*50)
    print("☕ 智能分拣系统 (Web 托管模式)")
    print("="*50)
    print(" ✅ 本地窗口已隐藏")
    print(" ✅ 浏览器关闭后程序将自动退出")
    print("="*50)

    try:
        while True:
            # --- 🔥 心跳检测机制 ---
            # 如果超过 3 秒没有收到前端的心跳包，且已经过了启动缓冲期
            if time.time() - state.last_heartbeat > 3.0:
                print("\n>>> 💔 检测到浏览器已关闭 (心跳丢失)")
                print(">>> 👋 程序正在退出...")
                break # 跳出循环，结束程序

            ret, frame = cap.read()
            if not ret: 
                time.sleep(0.1)
                continue
            
            # 1. 视觉处理
            processed_frame, offset = vision.process_frame(frame)
            
            # 2. UI 绘制 (为了 Web 显示)
            mode_str = f"MODE: {state.mode}"
            mode_color = (0, 0, 255) if state.mode == "CLEARING" else (0, 255, 0)
            
            cv2.putText(processed_frame, mode_str, (12, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
            cv2.putText(processed_frame, mode_str, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, mode_color, 2)
            
            if state.mode == "CLEARING":
                tip_str = "SELECT 1-6 TO CLEAR..."
                cv2.putText(processed_frame, tip_str, (12, 102), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
                cv2.putText(processed_frame, tip_str, (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            for i in range(1, 7):
                status = state.inventory[i]
                color = (0, 0, 255) if status == 1 else (0, 255, 0)
                cx = 50 + (i-1) * 60
                cy = 450
                cv2.circle(processed_frame, (cx, cy), 15, (0,0,0), -1)
                cv2.circle(processed_frame, (cx, cy), 13, color, -1)
                cv2.putText(processed_frame, str(i), (cx-5, cy+5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 2)
                label = "FULL" if status else "FREE"
                cv2.putText(processed_frame, label, (cx-20, cy+28), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,0), 3)
                cv2.putText(processed_frame, label, (cx-20, cy+28), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,255), 1)

            # 3. 推送画面
            web_server.update_frame(processed_frame)

            # 4. 处理 Web 指令
            if state.pending_ai_cmd:
                cmd = state.pending_ai_cmd
                print(f"🤖 [Main] 执行 Web 指令: {cmd}")
                
                if cmd.get('action') == 'go_home':
                    if state.mode != "EXECUTING":
                        arm.go_observe()
                    state.mode = "IDLE"
                
                elif cmd.get('action') == 'scan':
                    pass

                state.pending_ai_cmd = None
                if state.mode == "AI_WAIT":
                    state.mode = "IDLE"

            # 5. 自动模式逻辑
            fake_detect = (settings.SIMULATION_MODE and False)
            if state.mode == "AUTO" and (offset or fake_detect):
                target_slot = get_first_empty_slot()
                if target_slot:
                    print(f"🤖 [Auto] 触发分拣 -> {target_slot}号")
                    t = threading.Thread(target=perform_pick_and_place, args=(arm, target_slot))
                    t.start()
                    time.sleep(1.0) 
                else:
                    print("⚠️ 仓库已满，自动模式暂停")
                    state.mode = "IDLE"

            time.sleep(0.03)

    except KeyboardInterrupt:
        print("\n>>> 用户强制中断")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        # 确保 Web 线程也能退出（虽然是 daemon 但显式退出更好）
        sys.exit(0)

if __name__ == "__main__":
    main()