import cv2
import time
import threading
import sys
import os

from modules.vision import VisionSystem
from modules.arm_control import ArmController
from modules.ai_decision import AIDecisionMaker
from modules import web_server
from config import settings

class SystemState:
    def __init__(self):
        # 库存: 0=空(Empty), 1=满(Full)
        self.inventory = {i: 0 for i in range(1, 7)}
        # 模式: IDLE(空闲), AUTO(自动), EXECUTING(执行中), CLEARING(清除模式)
        self.mode = "IDLE" 
        self.pending_task = None 

state = SystemState()

def perform_pick_and_place(arm, target_slot):
    """
    工作线程：执行一次【固定点位】抓取放置
    """
    previous_mode = state.mode
    state.mode = "EXECUTING"
    
    try:
        # 1. 执行抓取
        arm.pick()

        # 2. 执行放置
        arm.place(target_slot)

        # 3. 更新库存
        state.inventory[target_slot] = 1
        print(f"✅ [System] {target_slot}号位 已满")

    except Exception as e:
        print(f"❌ [System] 执行出错: {e}")
        arm.go_observe()
    
    finally:
        # 恢复之前的模式
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
    
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if arm.mc:
        arm.go_observe()

    web_thread = threading.Thread(target=web_server.start_flask, args=(state, ai), daemon=True)
    web_thread.start()

    print("\n" + "="*50)
    print("☕ 智能分拣系统 (UI修复版)")
    print("="*50)
    print(" [ 1-6 ] : 抓取并放入指定槽位")
    print(" [  C  ] : 🧹 一键清空所有库存")
    print(" [  X  ] : 🗑️ 清除单个槽位")
    print(" [  A  ] : 🤖 自动模式开关")
    print(" [  R  ] : 🚀 强制归位")
    print(" [  Q  ] : 🚪 退出")
    print("="*50)

    while True:
        ret, frame = cap.read()
        if not ret: 
            time.sleep(0.1)
            continue
        
        # 1. 视觉处理 (Offset文字在 (10, 30))
        processed_frame, offset = vision.process_frame(frame)
        
        # 2. UI 绘制 (向下错开位置)
        
        # --- 模式显示 (下移到 Y=70) ---
        mode_str = f"MODE: {state.mode}"
        mode_color = (0, 0, 255) if state.mode == "CLEARING" else (0, 255, 0)
        
        # (技巧) 先画黑色描边，增加对比度，防止背景太亮看不清
        cv2.putText(processed_frame, mode_str, (12, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
        cv2.putText(processed_frame, mode_str, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, mode_color, 2)
        
        # --- 清除模式提示 (下移到 Y=100) ---
        if state.mode == "CLEARING":
            tip_str = "SELECT 1-6 TO CLEAR..."
            cv2.putText(processed_frame, tip_str, (12, 102), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
            cv2.putText(processed_frame, tip_str, (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # --- 库存状态 (底部) ---
        for i in range(1, 7):
            status = state.inventory[i]
            color = (0, 0, 255) if status == 1 else (0, 255, 0) # 红满绿空
            
            # 位置计算
            cx = 50 + (i-1) * 60
            cy = 450
            
            # 画圆点
            cv2.circle(processed_frame, (cx, cy), 15, (0,0,0), -1) # 黑底
            cv2.circle(processed_frame, (cx, cy), 13, color, -1)   # 彩芯
            
            # 画数字
            cv2.putText(processed_frame, str(i), (cx-5, cy+5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 2)
            
            # 画文字状态
            label = "FULL" if status else "FREE"
            cv2.putText(processed_frame, label, (cx-20, cy+28), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,0), 3) # 黑边
            cv2.putText(processed_frame, label, (cx-20, cy+28), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,255), 1)

        web_server.update_frame(processed_frame)
        cv2.imshow("Main Control", processed_frame)
        
        # 3. 键盘交互
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            break

        elif key == ord('r'):
            if state.mode != "EXECUTING":
                arm.go_observe()
        
        elif key == ord('a'):
            if state.mode == "AUTO":
                state.mode = "IDLE"
                print(">>> ⏸️ 自动模式已暂停")
            elif state.mode == "IDLE":
                state.mode = "AUTO"
                print(">>> ▶️ 进入自动流水线模式")

        elif key == ord('c'):
            state.inventory = {i: 0 for i in range(1, 7)}
            print("\n>>> 🧹 [系统] 库存状态已全部重置！")

        elif key == ord('x'):
            if state.mode == "IDLE" or state.mode == "AUTO":
                state.mode = "CLEARING"
                print("\n>>> 🗑️ [系统] 请按数字键 1-6 清除对应槽位...")
            elif state.mode == "CLEARING":
                state.mode = "IDLE"
                print(">>> 🔙 已退出清除模式")

        if ord('1') <= key <= ord('6'):
            slot_id = key - ord('0')

            if state.mode == "CLEARING":
                state.inventory[slot_id] = 0
                print(f">>> 🗑️ {slot_id}号位状态已手动清除。")
                state.mode = "IDLE"

            elif state.mode == "IDLE":
                if state.inventory[slot_id] == 1:
                    print(f"⚠️ {slot_id}号位显示已满！(按 'C' 清空或 'X' 单删)")
                else:
                    print(f"🚀 [手动] 启动搬运 -> {slot_id}号")
                    t = threading.Thread(target=perform_pick_and_place, args=(arm, slot_id))
                    t.start()

        if state.mode == "AUTO" and offset:
            target_slot = get_first_empty_slot()
            if target_slot:
                print(f"🤖 [Auto] 视觉触发 -> 分拣至 {target_slot}号")
                t = threading.Thread(target=perform_pick_and_place, args=(arm, target_slot))
                t.start()
                time.sleep(0.5) 
            else:
                print("⚠️ 仓库已满，自动模式暂停")
                state.mode = "IDLE"

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()