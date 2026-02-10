import cv2
import time
import threading
import sys
import os
import webbrowser
import random 

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
        self.inventory = {i: 0 for i in range(1, 7)}
        self.mode = "IDLE" 
        self.pending_ai_cmd = None 
        self.last_heartbeat = time.time() + 15.0
        self.system_msg = None
        self.current_task = None 

state = SystemState()

# 随机语录库 (纯文字，无 emoji)
SUCCESS_PHRASES = [
    "搞定，物品已移到{}号位。",
    "执行完毕，{}号位已归位。",
    "好了，东西已经放进{}号槽位了。",
    "完成任务，{}号位现在是满的。",
    "OK，物品已准确放入{}号位。"
]

def get_random_success_msg(slot_id):
    # 🔥 修改：不再加 ✅，直接返回文字
    phrase = random.choice(SUCCESS_PHRASES).format(slot_id)
    return phrase 

def perform_pick_and_place(arm, target_slot, active_mode="SINGLE_TASK", restore_mode="IDLE"):
    try:
        state.mode = active_mode
        arm.pick()
        
        if state.mode == "IDLE" and restore_mode != "IDLE":
            print(">>> [System] 检测到暂停")
            restore_mode = "IDLE"

        arm.place(target_slot)
        state.inventory[target_slot] = 1
        
        # 任务完成后，设置系统消息
        state.system_msg = get_random_success_msg(target_slot)
        print(f"✅ [System] {target_slot}号位 已满")

    except Exception as e:
        state.system_msg = f"❌ 出错: {e}"
        arm.go_observe()
        restore_mode = "IDLE" 
    
    finally:
        if state.mode == active_mode:
            state.mode = restore_mode

def get_first_empty_slot():
    for i in range(1, 7):
        if state.inventory[i] == 0: return i
    return None

def get_buffer_slot(reserved_slot):
    priority_order = [6, 5, 4, 3, 2, 1]
    for slot in priority_order:
        if slot == reserved_slot: continue
        if state.inventory[slot] == 0: return slot
    return None

def main():
    arm = ArmController()
    vision = VisionSystem()
    ai = AIDecisionMaker()
    
    if settings.SIMULATION_MODE:
        cap = MockCamera()
    else:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if arm.mc: arm.go_observe()

    web_thread = threading.Thread(target=web_server.start_flask, args=(state, ai), daemon=True)
    web_thread.start()

    print(">>> 🌐 Web 控制台已启动")
    time.sleep(1.0)
    webbrowser.open("http://127.0.0.1:5000")

    try:
        while True:
            # 🔥 修改点 1：移除心跳超时自动退出的逻辑
            # 原代码: if time.time() - state.last_heartbeat > 3.0: break
            
            # 🔥 修改点 2：改为“心跳超时自动暂停”，但保持程序运行
            if state.mode != "IDLE" and (time.time() - state.last_heartbeat > 5.0):
                print("⚠️ [System] 心跳丢失 (网页可能已关闭或后台挂起)，强制暂停机械臂")
                state.mode = "IDLE"
                state.current_task = None
                # 注意：这里不 break，程序继续跑，等你回来重连

            ret, frame = cap.read()
            if not ret: 
                time.sleep(0.1)
                continue
            
            processed_frame, vision_data = vision.process_frame(frame)
            
            if state.pending_ai_cmd:
                cmd = state.pending_ai_cmd
                cmd_action = cmd.get('action')
                cmd_type = cmd.get('type')
                
                print(f"🤖 [Main] CMD: {cmd}")

                if cmd_action == 'start':
                    if state.mode == "IDLE":
                        state.mode = "AUTO"
                        state.current_task = None 
                elif cmd_action == 'stop':
                    state.mode = "IDLE"
                    state.current_task = None
                elif cmd_action == 'reset':
                    if state.mode in ["IDLE"]:
                        arm.go_observe()
                        # 🔥 修改：去掉 emoji
                        state.system_msg = "机械臂已复位。"
                    else:
                        state.system_msg = "作业中无法复位。"
                elif cmd_action == 'clear_all':
                    if state.mode in ["IDLE"]:
                        state.inventory = {i: 0 for i in range(1, 7)}
                        # 🔥 修改：去掉 emoji
                        state.system_msg = "库存已清空。"
                    else:
                        state.system_msg = "作业中无法清空。"
                elif cmd_action == 'scan':
                    report = [f"{i}号{'满' if state.inventory[i] else '空'}" for i in range(1,7)]
                    state.system_msg = "库存: " + ", ".join(report)
                elif cmd_type == 'inventory_update':
                    sid = cmd.get('slot_id')
                    sts = cmd.get('status')
                    if sid:
                        state.inventory[sid] = sts
                        # 🔥 修改：去掉 emoji
                        state.system_msg = f"已更新{sid}号位状态。"

                elif cmd_type == 'sort':
                    target_slot = cmd.get('slot_id')
                    target_color = cmd.get('color', 'any').lower()
                    
                    if target_slot and 1 <= target_slot <= 6:
                        if state.inventory[target_slot] == 1:
                            state.system_msg = f"⚠️ {target_slot}号位已满。"
                        else:
                            state.current_task = {'slot': target_slot, 'color': target_color}
                            state.mode = "SORTING_TASK"
                            print(f"🤖 [Task] 目标锁定: {target_color} -> {target_slot}")
                    else:
                        state.system_msg = "⚠️ 无效槽位。"

                state.pending_ai_cmd = None

            web_server.update_frame(processed_frame)

            fake_detect = (settings.SIMULATION_MODE and False)
            is_detected = False
            detected_color = "unknown"
            if vision_data and vision_data.get("detected"):
                is_detected = True
                detected_color = vision_data.get("color", "unknown").lower()

            if state.mode == "AUTO" and (is_detected or fake_detect):
                target = get_first_empty_slot()
                if target:
                    state.mode = "EXECUTING" 
                    t = threading.Thread(target=perform_pick_and_place, args=(arm, target, "EXECUTING", "AUTO"))
                    t.start()
                    time.sleep(0.5)
                else:
                    state.mode = "IDLE"
                    state.system_msg = "⚠️ 仓库已满，自动停止。"

            elif state.mode == "SORTING_TASK" and (is_detected or fake_detect):
                task = state.current_task
                target_slot = task['slot']
                target_color = task['color']

                is_match = False
                if target_color == 'any': is_match = True
                elif detected_color == target_color: is_match = True
                
                if is_match:
                    print(f"🎯 匹配目标")
                    state.mode = "SINGLE_TASK"
                    t = threading.Thread(target=perform_pick_and_place, args=(arm, target_slot, "SINGLE_TASK", "IDLE"))
                    t.start()
                    state.current_task = None
                else:
                    buffer_slot = get_buffer_slot(reserved_slot=target_slot)
                    if buffer_slot:
                        state.system_msg = f"移走{detected_color}挡路物品..."
                        state.mode = "SINGLE_TASK"
                        t = threading.Thread(target=perform_pick_and_place, args=(arm, buffer_slot, "SINGLE_TASK", "SORTING_TASK"))
                        t.start()
                    else:
                        state.mode = "IDLE"
                        state.system_msg = "❌ 缓冲区满，任务终止。"
                        state.current_task = None
                time.sleep(0.5)
            time.sleep(0.03)

    except KeyboardInterrupt: pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        sys.exit(0)

if __name__ == "__main__":
    main()