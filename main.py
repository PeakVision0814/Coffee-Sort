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
        self.inventory = {i: 0 for i in range(1, 7)}
        self.mode = "IDLE" 
        self.pending_ai_cmd = None 
        self.last_heartbeat = time.time() + 15.0
        self.system_msg = None 

state = SystemState()

def perform_pick_and_place(arm, target_slot, active_mode="SINGLE_TASK", restore_mode="IDLE"):
    """
    工作线程：执行一次抓取放置
    """
    try:
        # 再次确认锁定状态
        state.mode = active_mode
        
        arm.pick()
        
        # 安全检查
        if state.mode == "IDLE" and restore_mode == "AUTO":
            print(">>> [System] 检测到暂停信号，任务完成后将停止")
            restore_mode = "IDLE"

        arm.place(target_slot)
        state.inventory[target_slot] = 1
        
        state.system_msg = f"✅ 执行完毕。物品已成功放入 {target_slot}号槽位。"
        print(f"✅ [System] {target_slot}号位 已满")

    except Exception as e:
        err_str = f"❌ 执行出错: {e}"
        print(f"[System] {err_str}")
        state.system_msg = err_str
        arm.go_observe()
        restore_mode = "IDLE" 
    
    finally:
        if state.mode == active_mode:
            state.mode = restore_mode
            print(f">>> [System] 任务结束，模式切换为: {state.mode}")
        else:
            print(f">>> [System] 任务结束，保持当前模式: {state.mode}")

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
        cap = MockCamera()
    else:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if arm.mc: arm.go_observe()

    web_thread = threading.Thread(target=web_server.start_flask, args=(state, ai), daemon=True)
    web_thread.start()

    print(">>> 🌐 正在打开 Web 控制台...")
    time.sleep(1.0)
    webbrowser.open("http://127.0.0.1:5000")

    print("\n" + "="*50)
    print("☕ 智能分拣系统 (Web 托管模式)")
    print("="*50)

    try:
        while True:
            if time.time() - state.last_heartbeat > 3.0:
                print("\n>>> 💔 检测到浏览器已关闭")
                break

            ret, frame = cap.read()
            if not ret: 
                time.sleep(0.1)
                continue
            
            # 🔥 修改 1: 适配新的 process_frame 返回值 (frame, result_dict)
            processed_frame, vision_data = vision.process_frame(frame)
            
            # --- 处理 Web/AI 指令 ---
            if state.pending_ai_cmd:
                cmd = state.pending_ai_cmd
                cmd_action = cmd.get('action')
                cmd_type = cmd.get('type')          
                
                print(f"🤖 [Main] 收到原始数据: {cmd}")

                # --- A: 系统指令 ---
                if cmd_action == 'start':
                    if state.mode == "IDLE":
                        state.mode = "AUTO"
                        print(">>> [CMD] 自动模式启动")
                
                elif cmd_action == 'stop':
                    state.mode = "IDLE"
                    print(">>> [CMD] 暂停请求已确认")

                elif cmd_action == 'reset' or cmd_action == 'go_home':
                    if state.mode in ["AUTO", "EXECUTING", "SINGLE_TASK"]:
                        msg = "⚠️ 无法复位：当前正在作业中，请先等待任务结束。"
                        print(msg)
                        state.system_msg = msg
                    else:
                        arm.go_observe()
                        state.mode = "IDLE"
                        state.system_msg = "✅ 机械臂已回到初始观测姿态。"
                
                elif cmd_action == 'clear_all':
                    if state.mode in ["AUTO", "EXECUTING", "SINGLE_TASK"]:
                        state.system_msg = "⚠️ 无法操作：作业中禁止清空库存数据。"
                    else:
                        state.inventory = {i: 0 for i in range(1, 7)}
                        state.system_msg = "🗑️ 数据已重置，所有库存状态已清空。"

                elif cmd_action == 'scan':
                    report = []
                    for i in range(1, 7):
                        status = "已满" if state.inventory[i] == 1 else "空闲"
                        report.append(f"{i}号[{status}]")
                    full_report = "📊 扫描完成，当前库存情况如下：\n" + "\n".join(report)
                    print(f">>> [Scan] {full_report}")
                    state.system_msg = full_report

                elif cmd_type == 'inventory_update':
                    slot_id = cmd.get('slot_id')
                    new_status = cmd.get('status')
                    if slot_id and isinstance(slot_id, int) and 1 <= slot_id <= 6:
                        state.inventory[slot_id] = new_status
                        status_text = "已满" if new_status == 1 else "空闲"
                        msg = f"✅ 已手动更新：{slot_id}号槽位状态设为 [{status_text}]"
                        print(f">>> [Inventory] {msg}")
                        state.system_msg = msg
                    else:
                        state.system_msg = f"⚠️ 更新失败：无效参数 {cmd}"

                # --- B: 分拣指令 ---
                elif cmd_type == 'sort':
                    slot_id = cmd.get('slot_id')
                    if slot_id and isinstance(slot_id, int) and 1 <= slot_id <= 6:
                        if state.mode != "IDLE":
                            state.system_msg = f"⚠️ 指令排队失败：系统正忙 (模式:{state.mode})。"
                        elif state.inventory[slot_id] == 1:
                            err_msg = f"⚠️ 无法执行：检测到 {slot_id}号槽位已经满了。"
                            print(err_msg)
                            state.system_msg = err_msg
                        else:
                            print(f"🤖 [AI] 触发单次分拣 -> {slot_id}号")
                            state.mode = "SINGLE_TASK"
                            t = threading.Thread(target=perform_pick_and_place, args=(arm, slot_id, "SINGLE_TASK", "IDLE"))
                            t.start()
                    else:
                        state.system_msg = f"⚠️ 指令错误：无效的槽位 ID ({slot_id})。"

                state.pending_ai_cmd = None

            web_server.update_frame(processed_frame)

            # --- 自动模式循环 ---
            fake_detect = (settings.SIMULATION_MODE and False)
            
            # 🔥 修改 2: 提取视觉检测结果
            is_detected = False
            detected_color = "unknown"
            
            if vision_data and vision_data.get("detected"):
                is_detected = True
                detected_color = vision_data.get("color", "unknown")

            # 🔥 修改 3: 使用 is_detected 作为触发条件
            if state.mode == "AUTO" and (is_detected or fake_detect):
                
                # 目前逻辑：只要看到东西，就找第一个空位放进去（暂不区分颜色）
                target_slot = get_first_empty_slot()
                
                if target_slot:
                    print(f"🤖 [Auto] 视觉检测到: [{detected_color}], 触发分拣 -> {target_slot}号")
                    
                    state.mode = "EXECUTING"
                    t = threading.Thread(target=perform_pick_and_place, args=(arm, target_slot, "EXECUTING", "AUTO"))
                    t.start()
                    
                    time.sleep(0.5) 
                else:
                    print("⚠️ 仓库已满，自动暂停")
                    state.system_msg = "⚠️ 仓库已满，流水线自动暂停"
                    state.mode = "IDLE"

            time.sleep(0.03)

    except KeyboardInterrupt:
        print("\n>>> 用户强制中断")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        sys.exit(0)

if __name__ == "__main__":
    main()