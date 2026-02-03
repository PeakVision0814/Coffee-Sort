import cv2
import time
import sys
import threading
from modules.vision import VisionSystem
from modules.arm_control import ArmController
from modules.ai_decision import AIDecisionMaker
from config import settings

# --- 全局状态管理 ---
class SystemState:
    def __init__(self):
        # 库存状态: 0=空(Empty), 1=满(Full)
        # 默认假设全空，启动后可选择扫描
        self.inventory = {i: 0 for i in range(1, 7)}
        
        # 运行模式: "IDLE"(空闲), "AUTO"(自动流水线), "AI_WAIT"(等待指令)
        self.mode = "IDLE"
        
        # AI 指令缓存 (用于模拟 Web 端传入)
        self.pending_ai_cmd = None

# 实例化全局状态
state = SystemState()

def draw_ui(frame, vision_offset):
    """
    在画面上绘制仪表盘：模式、库存状态、视觉锁定信息
    """
    # 1. 绘制左上角状态栏
    cv2.rectangle(frame, (0, 0), (250, 120), (0, 0, 0), -1) # 背景黑框
    
    # 显示模式
    mode_color = (0, 255, 0) if state.mode == "AUTO" else (0, 255, 255)
    cv2.putText(frame, f"MODE: {state.mode}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, mode_color, 2)
    
    # 显示视觉偏差
    if vision_offset:
        cv2.putText(frame, f"Offset: {vision_offset[0]:.1f}, {vision_offset[1]:.1f}", (10, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    else:
        cv2.putText(frame, "Searching...", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 100), 1)

    # 2. 绘制下方库存地图 (模拟 4+2 布局)
    # 假设前4个一排，后2个一排
    base_y = 400
    start_x = 50
    gap = 60
    
    cv2.putText(frame, "Inventory Map:", (start_x, base_y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    
    for i in range(1, 7):
        # 计算绘制坐标 (简单的可视化排布)
        if i <= 4:
            x = start_x + (i-1) * gap
            y = base_y
        else:
            x = start_x + (i-5) * gap + 30 # 第二排缩进一点
            y = base_y + 50
            
        # 颜色: 绿=空, 红=满
        color = (0, 255, 0) if state.inventory[i] == 0 else (0, 0, 255)
        
        cv2.circle(frame, (x, y), 20, color, -1)
        cv2.putText(frame, str(i), (x-5, y+5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)

def perform_inventory_scan(arm, vision, cap):
    """
    开机自检流程：机械臂依次走到 6 个槽位上方看一眼
    """
    print("\n🛰️ [系统] 启动全场库存扫描...")
    state.mode = "SCANNING"
    
    for i in range(1, 7):
        print(f"   -> 正在检查 {i} 号位...")
        
        # 1. 获取槽位坐标
        coords = arm.get_slot_coords(i)
        if not coords: continue
        
        # 2. 移动到槽位上方 (安全高度)
        check_pos = list(coords).copy()
        check_pos[2] = settings.SAFE_Z 
        arm.mc.send_coords(check_pos, 80, 1) # 速度80
        time.sleep(2.5) # 等待到位
        
        # 3. 视觉确认 (读取 5 帧防抖)
        detected = False
        for _ in range(5):
            ret, frame = cap.read()
            if not ret: continue
            
            # 使用 Aruco 识别
            ids = vision.detect_aruco_marker(frame)
            
            # 逻辑：如果看到了二维码 -> 说明是空的(0)
            #      如果没有二维码 -> 说明被挡住了，是满的(1)
            # 注意：这里需要你实际测试，如果二维码贴在底板上，被挡住就看不到了
            if ids: 
                # 还可以校验一下 id 是否等于 i，防止看串
                pass 
            else:
                # 没看到二维码，尝试用图像亮度辅助判断？或者直接认为满
                # 这里为了演示稳健性，如果完全没看到 Aruco，我们先假设它是满的
                # (实际调试时，请确保空槽位的二维码非常清晰)
                detected = True # 代表"检测到障碍物/满"
            
            time.sleep(0.05)
            
        # 更新状态
        # 逻辑：看到二维码(ids不为空) = 空(0); 没看到 = 满(1)
        # 这里 detected 变量逻辑反一下：ids存在 -> detected=False(没东西)
        is_full = 1 if not ids else 0
        state.inventory[i] = is_full
        print(f"      [结果] {i}号位: {'🔴 满' if is_full else '🟢 空'}")

    # 扫描结束，回原点
    arm.go_observe()
    print("✅ 扫描完成，库存已更新。\n")

def get_first_empty_slot():
    """查找第一个空槽位 (贪婪算法)"""
    for i in range(1, 7):
        if state.inventory[i] == 0:
            return i
    return None

def main():
    # 1. 初始化各模块
    arm = ArmController()
    vision = VisionSystem()
    ai = AIDecisionMaker()
    
    # 2. 打开摄像头
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # 3. 启动时的选择
    print(">>> 正在启动系统...")
    # 如果机械臂连接成功，询问是否扫描
    if arm.mc:
        # 这里为了演示方便，直接执行扫描，或者你可以注释掉这行
        # perform_inventory_scan(arm, vision, cap)
        arm.go_observe()
        state.mode = "AUTO" # 默认进入自动模式
    
    window_name = "Coffee Sorting System (AI Powered)"
    cv2.namedWindow(window_name)

    print("\n" + "="*40)
    print("   ☕ 智能分拣系统操作台")
    print("="*40)
    print(" [ A ] -> 切换到 AUTO (自动流水线)")
    print(" [ M ] -> 切换到 AI_WAIT (等待指令)")
    print(" [ S ] -> 强制重新扫描库存 (Scan)")
    print(" [ 1-6 ] -> (AI模式下) 模拟语音指令放几号")
    print(" [ Q ] -> 退出")
    print("="*40 + "\n")

    while True:
        ret, frame = cap.read()
        if not ret: 
            time.sleep(0.1)
            continue
            
        # 1. 视觉处理
        processed_frame, offset = vision.process_frame(frame)
        
        # 2. 绘制 UI
        draw_ui(processed_frame, offset)
        cv2.imshow(window_name, processed_frame)
        
        # 3. 监听键盘指令 (模拟前端/语音输入)
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            break
        elif key == ord('a'):
            state.mode = "AUTO"
            print(">>> 切换模式: AUTO (自动流水线)")
        elif key == ord('m'):
            state.mode = "AI_WAIT"
            print(">>> 切换模式: AI_WAIT (等待语音指令...)")
        elif key == ord('s'):
            if arm.mc:
                perform_inventory_scan(arm, vision, cap)
                state.mode = "IDLE" # 扫完待机
        
        # 模拟 AI 指令输入 (在 AI_WAIT 模式下按数字键)
        if state.mode == "AI_WAIT" and ord('1') <= key <= ord('6'):
            target_id = key - ord('0')
            print(f"👂 [模拟AI] 收到指令: 放入 {target_id} 号位")
            state.pending_ai_cmd = {"type": "sort", "slot_id": target_id}

        # --- 4. 核心状态机逻辑 ---
        
        # [逻辑 A] 自动模式：无脑抓取 -> 填空
        if state.mode == "AUTO":
            # 只有当：1.看到物体 2.且物体大概在画面中心(偏差小) 3.且机械臂空闲
            if offset:
                # 这里的逻辑可以优化：如果 offset 很小，说明在正下方，可以抓
                # 为了简化，只要识别到就触发抓取流程
                print(f"🎯 [AUTO] 发现目标，准备抓取...")
                
                # 1. 找个空位
                target_slot = get_first_empty_slot()
                if target_slot is None:
                    print("⚠️ [警告] 仓库已满！无法放置！请先清理或按 'S' 重置。")
                    # 这里可以加个蜂鸣器报警
                    state.mode = "IDLE" # 强制停止
                    continue
                
                # 2. 执行抓取 (这是个原子操作，会阻塞画面)
                current_coords = arm.mc.get_coords()
                if current_coords:
                    # 计算目标物理坐标
                    # 注意：这里的 offset 方向已经在 vision.py 调好了
                    pick_x = current_coords[0] + offset[0]
                    pick_y = current_coords[1] + offset[1]
                    
                    arm.pick(pick_x, pick_y)
                    arm.place(slot_id=target_slot)
                    
                    # 3. 更新库存
                    state.inventory[target_slot] = 1
                    print(f"✅ [库存] {target_slot} 号位已占用")
                else:
                    print("❌ 读取坐标失败，跳过本次")

        # [逻辑 B] AI 模式：等待指令
        elif state.mode == "AI_WAIT":
            if state.pending_ai_cmd:
                cmd = state.pending_ai_cmd
                state.pending_ai_cmd = None # 清除指令
                
                if cmd['type'] == 'sort':
                    slot_id = cmd['slot_id']
                    
                    # 1. 检查该位置是否空
                    if state.inventory.get(slot_id) == 1:
                        print(f"⚠️ [拒绝] {slot_id} 号位已满，AI 指令被驳回。")
                    else:
                        # 2. 寻找视觉目标 (必须先看到东西才能抓)
                        if offset:
                            print(f"🤖 [AI执行] 正在抓取并放入 {slot_id} 号...")
                            current_coords = arm.mc.get_coords()
                            pick_x = current_coords[0] + offset[0]
                            pick_y = current_coords[1] + offset[1]
                            
                            arm.pick(pick_x, pick_y)
                            arm.place(slot_id=slot_id)
                            
                            state.inventory[slot_id] = 1
                        else:
                            print("👀 [失败] AI 想抓，但视野里没有东西！")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()