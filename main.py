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
        # 🔥 新增：系统消息队列 (用于后端主动给前端发弹幕)
        self.system_msg = None 

state = SystemState()

# 🔥 修改：增加 active_mode 参数，区分是“自动运行中”还是“单次任务中”
def perform_pick_and_place(arm, target_slot, active_mode="SINGLE_TASK", restore_mode="IDLE"):
    """
    工作线程：执行一次抓取放置
    active_mode: 执行过程中系统显示的状态 (SINGLE_TASK / AUTO)
    restore_mode: 任务结束后系统应该恢复的模式 (IDLE / AUTO)
    """
    try:
        # 切换到“忙碌”状态
        state.mode = active_mode
        
        arm.pick()
        
        # 安全检查：如果在抓取过程中用户点了暂停 (mode 被改成了 IDLE)
        # 只有在全自动模式下才需要响应暂停，单次任务通常硬着头皮做完
        if state.mode == "IDLE" and restore_mode == "AUTO":
            print(">>> [System] 检测到暂停信号，任务完成后将停止")
            restore_mode = "IDLE"

        arm.place(target_slot)
        state.inventory[target_slot] = 1
        
        # 🔥 成功反馈：直接推送到聊天框
        state.system_msg = f"✅ 执行完毕。物品已成功放入 {target_slot}号槽位。"
        print(f"✅ [System] {target_slot}号位 已满")

    except Exception as e:
        err_str = f"❌ 执行出错: {e}"
        print(f"[System] {err_str}")
        state.system_msg = err_str
        arm.go_observe()
        restore_mode = "IDLE" 
    
    finally:
        # 任务结束，恢复状态
        # 只有当前没被强制打断时，才恢复
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
            
            processed_frame, offset = vision.process_frame(frame)
            
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

                # ... (前面代码不变)

                elif cmd_action == 'reset' or cmd_action == 'go_home':
                    if state.mode in ["AUTO", "SINGLE_TASK"]:
                        # 拟人化拒绝
                        msg = "⚠️ 无法复位：当前正在作业中，请先等待任务结束。"
                        print(msg)
                        state.system_msg = msg
                    else:
                        arm.go_observe()
                        state.mode = "IDLE"
                        # 拟人化成功
                        state.system_msg = "✅ 机械臂已回到初始观测姿态。"
                
                elif cmd_action == 'clear_all':
                    if state.mode in ["AUTO", "SINGLE_TASK"]:
                        state.system_msg = "⚠️ 无法操作：作业中禁止清空库存数据。"
                    else:
                        state.inventory = {i: 0 for i in range(1, 7)}
                        state.system_msg = "🗑️ 数据已重置，所有库存状态已清空。"

                # --- 扫描逻辑 ---
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
                    new_status = cmd.get('status') # 0 or 1
                    
                    if slot_id and isinstance(slot_id, int) and 1 <= slot_id <= 6:
                        # 更新内存状态
                        state.inventory[slot_id] = new_status
                        
                        status_text = "已满" if new_status == 1 else "空闲"
                        msg = f"✅ 已手动更新：{slot_id}号槽位状态设为 [{status_text}]"
                        print(f">>> [Inventory] {msg}")
                        state.system_msg = msg
                    else:
                        state.system_msg = f"⚠️ 更新失败：无效参数 {cmd}"


                # --- 分拣逻辑 ---
                elif cmd_type == 'sort':
                    slot_id = cmd.get('slot_id')
                    
                    if slot_id and isinstance(slot_id, int) and 1 <= slot_id <= 6:
                        if state.mode != "IDLE":
                            state.system_msg = f"⚠️ 指令排队失败：系统正忙 (模式:{state.mode})。"
                        
                        elif state.inventory[slot_id] == 1:
                            # 🔥 拟人化报错
                            err_msg = f"⚠️ 无法执行：检测到 {slot_id}号槽位已经满了。"
                            print(err_msg)
                            state.system_msg = err_msg
                        
                        else:
                            print(f"🤖 [AI] 触发单次分拣 -> {slot_id}号")
                            state.mode = "EXECUTING"
                            t = threading.Thread(target=perform_pick_and_place, args=(arm, slot_id, "SINGLE_TASK", "IDLE"))
                            t.start()
                    else:
                        state.system_msg = f"⚠️ 指令错误：无效的槽位 ID ({slot_id})。"

                # ... (后面代码不变)

                state.pending_ai_cmd = None

            web_server.update_frame(processed_frame)

            # --- 自动模式循环 ---
            fake_detect = (settings.SIMULATION_MODE and False)
            
            # 只有 AUTO 模式才自动触发
            if state.mode == "AUTO" and (offset or fake_detect):
                target_slot = get_first_empty_slot()
                if target_slot:
                    print(f"🤖 [Auto] 触发分拣 -> {target_slot}号")
                    # 自动模式下，执行时状态依然算 AUTO (或细分为 AUTO_RUNNING)
                    # 这里为了配合 app.js，我们保持 AUTO 即可，或者用 SINGLE_TASK 但 app.js 认为是自动
                    # 简单起见，这里不需要改 state.mode，perform_pick_and_place 会设为 active_mode
                    
                    t = threading.Thread(target=perform_pick_and_place, args=(arm, target_slot, "AUTO", "AUTO"))
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