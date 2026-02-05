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
        # 我们不再需要 ai_enabled 变量，前端直接根据 mode 判断互斥

state = SystemState()

def perform_pick_and_place(arm, target_slot):
    previous_mode = state.mode
    state.mode = "EXECUTING"
    try:
        arm.pick()
        # --- 粗颗粒度安全检查 ---
        # 如果在抓取过程中用户点了暂停，state.mode 会变成 IDLE (虽然这里被覆盖了，但全局会被改)
        # 但为了安全，一旦抓起来了，必须放下，不能停在半空。
        # 所以这里我们不检测暂停，必须跑完。
        
        arm.place(target_slot)
        state.inventory[target_slot] = 1
        print(f"✅ [System] {target_slot}号位 已满")

    except Exception as e:
        print(f"❌ [System] 执行出错: {e}")
        arm.go_observe()
    
    finally:
        # 任务结束
        # 关键逻辑：如果任务开始前是 AUTO，且中间没有被改为 IDLE，那就保持 AUTO
        # 但如果用户中间按了暂停，main loop 会把 pending_task 处理掉并把 mode 设为 IDLE
        # 这里的线程内局部变量 previous_mode 可能过时了。
        
        # 修正逻辑：
        # 只有当全局模式依然是 EXECUTING (意味着没人打断) 时，才恢复 AUTO
        # 如果用户点了暂停，全局模式已经被改成了 IDLE (在 main loop 里)，这里就不应该改回 AUTO
        pass 
        # 实际上由 main loop 控制状态流转更安全，这里只负责把 EXECUTING 拿掉
        
        # 简单处理：线程结束，状态交给 main loop 决定
        # 如果本来是 AUTO，跑完这一单，main loop 发现还是 AUTO，就会起新线程。
        # 如果用户点了 Stop，main loop 会把 mode 改成 IDLE。
        # 唯一的问题是：main loop 此时是 EXECUTING，它不会改状态。
        
        # 最终方案：
        if state.mode == "EXECUTING":
            # 如果没被外部打断，恢复为 AUTO，让 main loop 继续跑
            state.mode = "AUTO"
        else:
            # 如果被改成了 IDLE (说明用户点了暂停)，那就保持 IDLE
            print(">>> [System] 动作完成，响应暂停指令，停止流水线。")

def get_first_empty_slot():
    for i in range(1, 7):
        if state.inventory[i] == 0: return i
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
            
            # --- 处理指令 ---
            if state.pending_ai_cmd:
                cmd = state.pending_ai_cmd
                action = cmd.get('action')
                print(f"🤖 [Main] 收到指令: {action}")
                
                if action == 'start':
                    if state.mode == "IDLE":
                        state.mode = "AUTO"
                        print(">>> [CMD] 自动模式启动")
                
                elif action == 'stop':
                    # 关键：如果正在执行，不要强制改为 IDLE，否则线程里的 finally 会乱
                    # 我们做一个标记，或者直接改。
                    # 刚才的线程逻辑是：if state.mode == "EXECUTING" -> AUTO
                    # 所以这里我们把 mode 强制改为 IDLE。
                    # 线程里的 finally 检测到 mode 不是 EXECUTING 了，就不会恢复 AUTO。
                    state.mode = "IDLE"
                    print(">>> [CMD] 暂停请求已确认 (将在当前动作完成后停止)")

                elif action == 'go_home':
                    if state.mode != "EXECUTING": arm.go_observe()
                    state.mode = "IDLE"
                
                elif action == 'clear_all':
                    state.inventory = {i: 0 for i in range(1, 7)}

                state.pending_ai_cmd = None

            web_server.update_frame(processed_frame)

            # 自动模式触发
            fake_detect = (settings.SIMULATION_MODE and False)
            
            # 只有在 mode 为 AUTO 时才触发新任务
            # 如果是 EXECUTING，说明正在跑，不触发
            # 如果是 IDLE，说明暂停了，不触发
            if state.mode == "AUTO" and (offset or fake_detect):
                target_slot = get_first_empty_slot()
                if target_slot:
                    print(f"🤖 [Auto] 触发分拣 -> {target_slot}号")
                    t = threading.Thread(target=perform_pick_and_place, args=(arm, target_slot))
                    t.start()
                    # 给一点时间让线程把状态改为 EXECUTING
                    time.sleep(0.5) 
                else:
                    print("⚠️ 仓库已满，自动暂停")
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