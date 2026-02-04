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
        self.inventory = {i: 0 for i in range(1, 7)}
        self.mode = "IDLE" 
        self.pending_task = None 

state = SystemState()

def perform_pick_and_place(arm, target_slot):
    """
    工作线程：执行一次【固定点位】抓取放置
    不再接受 vision_offset，完全盲抓
    """
    state.mode = "EXECUTING"
    
    try:
        # 1. 执行抓取 (无参，去默认点)
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
    print("☕ 智能分拣系统 (盲抓版)")
    print("="*50)
    print(" [ 1-6 ] : 手动触发 - 抓取并放入指定槽位")
    print(" [  A  ] : 自动模式 - 视觉检测到物体后自动抓取")
    print(" [  R  ] : 归位")
    print(" [  Q  ] : 退出")
    print("="*50)

    while True:
        ret, frame = cap.read()
        if not ret: 
            time.sleep(0.1)
            continue
        
        # 1. 视觉处理 (仅用于 UI 显示和自动模式触发判断)
        processed_frame, offset = vision.process_frame(frame)
        
        cv2.putText(processed_frame, f"MODE: {state.mode}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        inv_str = " ".join([f"{k}:{'FULL' if v else '_'}" for k,v in state.inventory.items()])
        cv2.putText(processed_frame, inv_str, (10, 460), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        web_server.update_frame(processed_frame)
        cv2.imshow("Main Control", processed_frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            break
        elif key == ord('r'):
            if state.mode != "EXECUTING":
                arm.go_observe()
        
        elif key == ord('a'):
            state.mode = "AUTO" if state.mode != "AUTO" else "IDLE"
            print(f">>> 模式切换: {state.mode}")

        # 2. 手动指令 (1-6)
        if state.mode == "IDLE" and (ord('1') <= key <= ord('6')):
            slot_id = key - ord('0')
            if state.inventory[slot_id] == 1:
                print(f"⚠️ {slot_id}号位已满")
            else:
                print(f"🚀 [手动] 启动任务 -> {slot_id}号")
                t = threading.Thread(target=perform_pick_and_place, args=(arm, slot_id))
                t.start()

        # 3. 自动模式 (视觉作为开关)
        if state.mode == "AUTO" and offset:
            # offset 不为 None，说明视野里有东西
            # 我们不关心东西具体在哪里，只要有东西，就去默认点抓
            target_slot = get_first_empty_slot()
            
            if target_slot:
                print(f"🤖 [Auto] 视觉触发 -> 分拣至 {target_slot}号")
                t = threading.Thread(target=perform_pick_and_place, args=(arm, target_slot))
                t.start()
                time.sleep(1.0) # 简单防抖
            else:
                print("⚠️ 仓库已满")
                state.mode = "IDLE"

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()