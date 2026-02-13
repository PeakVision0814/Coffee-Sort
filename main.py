# -*- coding: utf-8 -*-
# Copyright (c) 2026 Hangzhou Zhicheng Technology Co., Ltd. All rights reserved.
# 
# This code is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.
# 
# System: Coffee Intelligent Sorting System
# Author: Hangzhou Zhicheng Technology Co., Ltd
# main.py

# -*- coding: utf-8 -*-
# Copyright (c) 2026 Hangzhou Zhicheng Technology Co., Ltd. All rights reserved.
# System: Coffee Intelligent Sorting System
# File: main.py

import cv2
import time
import threading
import sys
import os
import webbrowser
import random 
import logging
from logging.handlers import RotatingFileHandler

# --- 自定义模块导入 ---
from modules.vision import VisionSystem
from modules.arm_control import ArmController
from modules.ai_decision import AIDecisionMaker
from modules import web_server
from modules.plc_comm import PLCClient  # PLC 客户端
from config import settings

# --- 模拟模式兼容 ---
if settings.SIMULATION_MODE:
    from modules.mock_hardware import MockCamera
else:
    MockCamera = None

# ================= 配置日志系统 =================
LOG_FILE_PATH = os.path.join("logs", "system.log")
if not os.path.exists("logs"):
    os.makedirs("logs")

logger = logging.getLogger("CoffeeSystem")
logger.setLevel(logging.INFO)

# 轮转日志：最大 2MB，保留 5 个备份
file_handler = RotatingFileHandler(
    LOG_FILE_PATH, maxBytes=2*1024*1024, backupCount=5, encoding='utf-8'
)
file_formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)

if not logger.handlers:
    logger.addHandler(file_handler)

def log_msg(level, module, message):
    """同时输出到控制台(带时间)和日志文件"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    log_content = f"[{module}] {message}"
    
    if level == "INFO": logger.info(log_content)
    elif level == "WARN": logger.warning(log_content)
    elif level == "ERROR": logger.error(log_content)
    
    return f"[{timestamp}] {level} [{module}] {message}"

# ================= 系统状态类 =================
class SystemState:
    def __init__(self):
        # 库存状态 (1-6号槽位)
        self.inventory = {i: 0 for i in range(1, 7)}
        # 系统模式: IDLE, AUTO, SORTING_TASK, EXECUTING, SINGLE_TASK
        self.mode = "IDLE" 
        # 待处理的 AI 指令队列
        self.pending_ai_cmd = None 
        # 心跳时间
        self.last_heartbeat = time.time() + 15.0
        # UI 显示的消息
        self.system_msg = None
        # 当前指定的任务 (颜色/槽位)
        self.current_task = None
        # 🔥 关键状态位：标记机械臂是否位于观测点且准备好识别
        self.is_at_observe = False 

state = SystemState()

# 标准化成功提示语
SUCCESS_PHRASES = [
    "Task completed. Item placed in Slot {}.",
    "Operation successful. Slot {} occupied.",
    "Sort execution finished -> Slot {}.",
    "Item stored in Slot {}. Returning to IDLE."
]

def get_standard_success_msg(slot_id):
    return random.choice(SUCCESS_PHRASES).format(slot_id)

# ================= 核心工作线程 =================
def perform_pick_and_place(arm, target_slot, active_mode="SINGLE_TASK", restore_mode="IDLE"):
    """
    执行完整的 [抓取 -> 放置 -> 归位] 流程
    注意：此函数在独立线程中运行，属于阻塞操作
    """
    try:
        # 🔥 1. 动作开始：立即锁死视觉权限
        # 机械臂离开观测点，视觉数据不再可靠，必须屏蔽
        state.is_at_observe = False
        state.mode = active_mode
        
        # --- 执行抓取 (Arm内部处理 High-Mid-Low 轨迹) ---
        arm.pick()
        
        # 检查是否被中断
        if state.mode == "IDLE" and restore_mode != "IDLE":
            print(log_msg("WARN", "System", "Interrupt detected during pick operation."))
            restore_mode = "IDLE"

        # --- 执行放置 (Arm内部处理 High-Mid-Low 轨迹) ---
        arm.place(target_slot)
        
        # 软件层面暂时更新库存 (下一帧会被 PLC 真实数据覆盖)
        state.inventory[target_slot] = 1
        
        # 更新消息
        state.system_msg = get_standard_success_msg(target_slot)
        print(log_msg("INFO", "System", f"Slot {target_slot} mission complete."))

    except Exception as e:
        state.system_msg = f"❌ Error: {e}"
        print(log_msg("ERROR", "System", f"Pick & Place failed: {e}"))
        # 发生错误也尝试归位，但不保证成功
        try: arm.go_observe()
        except: pass
        restore_mode = "IDLE" 
    
    finally:
        # 🔥 2. 动作结束：强制物理归位
        # 只有回到观测点，才允许下一次视觉识别
        print(log_msg("INFO", "System", "Returning to Observe Point..."))
        arm.go_observe() 
        
        # 🔥 3. 归位完成：解锁视觉权限
        state.is_at_observe = True
        
        # 恢复之前的模式 (例如从 EXECUTING 恢复到 AUTO)
        if state.mode == active_mode:
            state.mode = restore_mode

# ================= 辅助函数 =================
def get_first_empty_slot():
    """获取第一个空闲槽位 (1-6)"""
    for i in range(1, 7):
        if state.inventory[i] == 0: return i
    return None

def get_buffer_slot(reserved_slot):
    """获取缓冲槽位 (倒序查找，避开目标槽位)"""
    priority_order = [6, 5, 4, 3, 2, 1]
    for slot in priority_order:
        if slot == reserved_slot: continue
        if state.inventory[slot] == 0: return slot
    return None

# ================= 主程序入口 =================
def main():
    # 1. 初始化硬件模块
    arm = ArmController()
    vision = VisionSystem()
    ai = AIDecisionMaker()
    
    # 2. 连接 PLC (物理世界的真理)
    print(log_msg("INFO", "System", "Connecting to PLC (192.168.0.10)..."))
    plc = PLCClient(ip='192.168.0.10')
    
    # 3. 初始化摄像头
    if settings.SIMULATION_MODE:
        cap = MockCamera()
    else:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # 4. 机械臂初始归位
    if arm.mc:
        print(log_msg("INFO", "System", "Initial Homing..."))
        arm.go_observe()
        state.is_at_observe = True # 标记已就绪

    # 5. 启动 Web 服务器
    web_thread = threading.Thread(target=web_server.start_flask, args=(state, ai), daemon=True)
    web_thread.start()

    print(log_msg("INFO", "Web", "Console started at http://127.0.0.1:5000"))
    time.sleep(1.0)
    webbrowser.open("http://127.0.0.1:5000")

    print(log_msg("INFO", "System", "System Ready. Waiting for commands..."))

    try:
        while True:
            # --- A. 心跳检测 ---
            if state.mode != "IDLE" and (time.time() - state.last_heartbeat > 5.0):
                print(log_msg("WARN", "System", "Heartbeat lost. Forcing IDLE mode."))
                state.mode = "IDLE"
                state.current_task = None
                state.system_msg = "⚠️ Connection lost. System paused."

            # --- B. 实时同步 PLC 状态 (核心真理) ---
            # 每一帧都以 PLC 读数为准，覆盖任何软件推测
            real_inventory = plc.get_slots_status()
            if real_inventory:
                state.inventory = real_inventory
            
            # --- C. 视觉处理 ---
            ret, frame = cap.read()
            if not ret: 
                time.sleep(0.1); continue
            
            processed_frame, vision_data = vision.process_frame(frame)
            web_server.update_frame(processed_frame) # 更新网页画面

            # --- D. AI 指令处理 ---
            if state.pending_ai_cmd:
                cmd_list = state.pending_ai_cmd
                print(log_msg("INFO", "Main", f"Received Batch CMDs: {len(cmd_list)}"))

                for cmd in cmd_list:
                    cmd_action = cmd.get('action')
                    cmd_type = cmd.get('type')

                    # 1. 修正库存 (手动覆盖)
                    if cmd_type == 'inventory_update':
                        sid = cmd.get('slot_id')
                        sts = cmd.get('status')
                        if sid == 0: # 批量
                            for i in range(1, 7): state.inventory[i] = sts
                            print(log_msg("INFO", "System", f"Manual override: ALL -> {sts}"))
                        elif sid in state.inventory:
                            state.inventory[sid] = sts
                            print(log_msg("INFO", "System", f"Manual override: Slot {sid} -> {sts}"))

                    # 2. 指定分拣任务
                    elif cmd_type == 'sort':
                        target_slot = cmd.get('slot_id')
                        target_color = cmd.get('color', 'any').lower()
                        # 检查 PLC 状态，如果是空的才接受任务
                        if target_slot and state.inventory.get(target_slot) == 0:
                            state.current_task = {'slot': target_slot, 'color': target_color}
                            state.mode = "SORTING_TASK"
                            print(log_msg("INFO", "Task", f"Sorting {target_color} to Slot {target_slot}"))
                        else:
                            state.system_msg = f"⚠️ Slot {target_slot} is FULL."
                            print(log_msg("WARN", "System", f"Sort rejected: Slot {target_slot} full."))

                    # 3. 系统控制
                    elif cmd_action == 'start':
                        if state.mode == "IDLE":
                            # 启动前先归位
                            if not state.is_at_observe: arm.go_observe(); state.is_at_observe = True
                            state.mode = "AUTO"
                            state.system_msg = "Auto-mode ON."
                            print(log_msg("INFO", "System", "Mode switched to AUTO"))
                    elif cmd_action == 'stop':
                        state.mode = "IDLE"; state.system_msg = "System STOPPED."
                    elif cmd_action == 'reset':
                        arm.go_observe(); state.is_at_observe = True; state.system_msg = "Arm RESET."
                    elif cmd_action == 'clear_all':
                        # 注意：PLC会覆盖这个，仅作为软件层面的临时清除
                        state.inventory = {i: 0 for i in range(1, 7)}

                state.pending_ai_cmd = None

            # --- E. 自动化作业触发逻辑 (核心修改) ---
            
            # 只有当机械臂在观测点(is_at_observe=True)时，才允许提取视觉检测结果
            # 这样可以防止机械臂运动时产生的阴影或误触
            trigger_detected = False
            detected_color = "unknown"

            if state.is_at_observe and vision_data and vision_data.get("detected"):
                trigger_detected = True
                detected_color = vision_data.get("color", "unknown").lower()
            
            # 场景 1: AUTO 模式 (见空就放)
            if state.mode == "AUTO" and trigger_detected:
                target = get_first_empty_slot()
                if target:
                    # 🔥 触发瞬间：立即关闭权限，防止线程启动间隙重复触发
                    state.is_at_observe = False 
                    state.mode = "EXECUTING" 
                    
                    # 启动独立线程执行搬运
                    t = threading.Thread(target=perform_pick_and_place, args=(arm, target, "EXECUTING", "AUTO"))
                    t.start()
                    # 稍微给点延时让线程跑起来
                    time.sleep(0.5)
                else:
                    state.mode = "IDLE"
                    state.system_msg = "⚠️ Warehouse FULL. Auto-stop."
                    print(log_msg("WARN", "System", "All slots full. Stopping pipeline."))

            # 场景 2: 指定任务模式 (只抓特定颜色)
            elif state.mode == "SORTING_TASK" and trigger_detected:
                task = state.current_task
                target_slot = task['slot']
                target_color = task['color']

                is_match = False
                if target_color == 'any': is_match = True
                elif detected_color == target_color: is_match = True
                
                if is_match:
                    print(log_msg("INFO", "Vision", f"Target match ({detected_color}). Executing sort."))
                    # 🔥 触发瞬间：关闭权限
                    state.is_at_observe = False
                    state.mode = "SINGLE_TASK"
                    
                    t = threading.Thread(target=perform_pick_and_place, args=(arm, target_slot, "SINGLE_TASK", "IDLE"))
                    t.start()
                    state.current_task = None
                else:
                    # 颜色不匹配，需要缓冲 (保持原有逻辑)
                    buffer_slot = get_buffer_slot(reserved_slot=target_slot)
                    if buffer_slot:
                        state.system_msg = f"Moving obstruction ({detected_color})..."
                        state.is_at_observe = False # 同样要锁定
                        state.mode = "SINGLE_TASK"
                        t = threading.Thread(target=perform_pick_and_place, args=(arm, buffer_slot, "SINGLE_TASK", "SORTING_TASK"))
                        t.start()
                        print(log_msg("INFO", "System", f"Buffering {detected_color} item to Slot {buffer_slot}"))
                    else:
                        state.mode = "IDLE"
                        state.system_msg = "❌ Buffer full. Task aborted."
                        state.current_task = None
                
                time.sleep(0.5)

            # 短暂休眠，降低 CPU 占用
            time.sleep(0.03)

    except KeyboardInterrupt:
        print(log_msg("INFO", "System", "User interrupted. Shutting down..."))
    finally:
        # 退出时资源清理
        if 'plc' in locals(): plc.close()
        cap.release()
        cv2.destroyAllWindows()
        sys.exit(0)

if __name__ == "__main__":
    main()