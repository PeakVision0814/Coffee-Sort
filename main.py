# -*- coding: utf-8 -*-
# Copyright (c) 2026 Hangzhou Zhicheng Technology Co., Ltd. All rights reserved.
# 
# This code is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.
# 
# System: Coffee Intelligent Sorting System
# Author: Hangzhou Zhicheng Technology Co., Ltd
# main.py
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
from modules.plc_comm import PLCClient
from config import settings

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

file_handler = RotatingFileHandler(
    LOG_FILE_PATH, maxBytes=2*1024*1024, backupCount=5, encoding='utf-8'
)
file_formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)

if not logger.handlers:
    logger.addHandler(file_handler)

def log_msg(level, module, message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    log_content = f"[{module}] {message}"
    if level == "INFO": logger.info(log_content)
    elif level == "WARN": logger.warning(log_content)
    elif level == "ERROR": logger.error(log_content)
    return f"[{timestamp}] {level} [{module}] {message}"

# ================= 系统状态类 =================
class SystemState:
    def __init__(self):
        self.inventory = {i: 0 for i in range(1, 7)}
        # 模式包括: IDLE, AUTO, SORTING_TASK, EXECUTING, SINGLE_TASK, EMERGENCY_STOP
        self.mode = "IDLE" 
        self.pending_ai_cmd = None 
        self.last_heartbeat = time.time() + 15.0
        self.system_msg = None
        self.current_task = None
        self.is_at_observe = False 

state = SystemState()

SUCCESS_PHRASES = [
    "Task completed. Item placed in Slot {}.",
    "Operation successful. Slot {} occupied."
]

def get_standard_success_msg(slot_id):
    return random.choice(SUCCESS_PHRASES).format(slot_id)

# ================= 核心工作线程 =================
def perform_pick_and_place(arm, target_slot, active_mode="SINGLE_TASK", restore_mode="IDLE"):
    """执行完整的搬运流程 (增加安全检查)"""
    try:
        # 🔥 安全检查 1: 动作开始前
        if state.mode == "EMERGENCY_STOP": raise Exception("Emergency Stop Active")
        
        state.is_at_observe = False
        state.mode = active_mode
        
        # --- 抓取 ---
        # 🔥 安全检查 2: 抓取前再次确认
        if state.mode == "EMERGENCY_STOP": raise Exception("Emergency Stop Active")
        arm.pick()
        
        if state.mode == "IDLE" and restore_mode != "IDLE":
            print(log_msg("WARN", "System", "Interrupt detected."))
            restore_mode = "IDLE"

        # --- 放置 ---
        # 🔥 安全检查 3: 放置前再次确认
        if state.mode == "EMERGENCY_STOP": raise Exception("Emergency Stop Active")
        arm.place(target_slot)
        
        state.inventory[target_slot] = 1
        state.system_msg = get_standard_success_msg(target_slot)
        print(log_msg("INFO", "System", f"Slot {target_slot} mission complete."))

    except Exception as e:
        state.system_msg = f"❌ Error: {e}"
        print(log_msg("ERROR", "System", f"Process Stopped: {e}"))
        # 只有在非急停状态下才尝试归位
        if state.mode != "EMERGENCY_STOP":
            try: arm.go_observe()
            except: pass
        restore_mode = "IDLE" 
    
    finally:
        # 🔥 安全检查 4: 如果是急停，禁止归位，保持现场
        if state.mode != "EMERGENCY_STOP":
            print(log_msg("INFO", "System", "Returning to Observe Point..."))
            arm.go_observe() 
            state.is_at_observe = True
            
            if state.mode == active_mode:
                state.mode = restore_mode
        else:
            print(log_msg("WARN", "System", "⚠️ Stopped in place due to Emergency."))

# ================= 辅助函数 =================
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

# ================= 主程序入口 =================
def main():
    arm = ArmController()
    vision = VisionSystem()
    ai = AIDecisionMaker()
    
    print(log_msg("INFO", "System", "Connecting to PLC (Ethernet)..."))
    plc = PLCClient(ip='192.168.0.10')
    
    if settings.SIMULATION_MODE:
        cap = MockCamera()
    else:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # 🔥 启动时的安全逻辑:
    # 只有当启动信号存在时，才允许初始归位
    if arm.mc:
        if arm.is_start_signal_active():
            print(log_msg("INFO", "System", "Start Signal OK. Initial Homing..."))
            arm.go_observe()
            state.is_at_observe = True
        else:
            print(log_msg("WARN", "System", "⚠️ No Start Signal on Boot. Waiting..."))
            state.mode = "EMERGENCY_STOP" # 初始锁死
            state.system_msg = "WAITING FOR START SIGNAL"

    web_thread = threading.Thread(target=web_server.start_flask, args=(state, ai), daemon=True)
    web_thread.start()
    
    print(log_msg("INFO", "Web", "Console at http://127.0.0.1:5000"))
    time.sleep(1.0)
    webbrowser.open("http://127.0.0.1:5000")

    try:
        while True:
            # ==========================================
            # 🔥 SECTION 0: 硬件安全与信号监控 (最高优先级)
            # ==========================================
            
            # 1. 检测启动信号 (G36)
            # 假设: 1=正常, 0=急停
            is_start_ok = arm.is_start_signal_active()

            # [情况 A]: 运行中信号丢失 -> 急停
            if not is_start_ok:
                if state.mode != "EMERGENCY_STOP":
                    print(log_msg("ERROR", "System", "🛑 START SIGNAL LOST! EMERGENCY STOP!"))
                    arm.emergency_stop()      # 硬件急停
                    state.mode = "EMERGENCY_STOP"
                    state.is_at_observe = False
                    state.system_msg = "🛑 HALTED: Check Start Signal"
                
                # 信号丢失期间，检查复位也没用(通常逻辑)，必须等启动信号回来
                time.sleep(0.1)
                continue # 跳过后面所有逻辑，死循环等待

            # [情况 B]: 信号已恢复，但系统仍在急停状态 -> 等待复位信号
            if is_start_ok and state.mode == "EMERGENCY_STOP":
                state.system_msg = "⚠️ Signal OK. Press RESET to resume."
                
                # 检测复位信号 (G35)
                if arm.is_reset_signal_active():
                    print(log_msg("INFO", "System", "🔄 Reset Signal Detected. Homing..."))
                    arm.go_observe() # 复位动作：归位
                    state.is_at_observe = True
                    state.mode = "IDLE"
                    state.system_msg = "System Resumed (IDLE)"
                    print(log_msg("INFO", "System", "System Resumed."))
                    time.sleep(1.0) # 防止长按复位键重复触发
                else:
                    time.sleep(0.1)
                    continue # 等待复位

            # ==========================================
            # 🔥 SECTION 1: 正常业务逻辑
            # ==========================================

            # --- 心跳检测 ---
            if state.mode != "IDLE" and state.mode != "EMERGENCY_STOP" and (time.time() - state.last_heartbeat > 5.0):
                print(log_msg("WARN", "System", "Heartbeat lost. Forcing IDLE mode."))
                state.mode = "IDLE"

            # --- 同步 PLC 库存 ---
            real_inventory = plc.get_slots_status()
            if real_inventory: state.inventory = real_inventory
            
            # --- 视觉处理 ---
            ret, frame = cap.read()
            if not ret: time.sleep(0.1); continue
            processed_frame, vision_data = vision.process_frame(frame)
            web_server.update_frame(processed_frame)

            # --- AI 指令 ---
            if state.pending_ai_cmd:
                cmd_list = state.pending_ai_cmd
                state.pending_ai_cmd = None # 取出后清空
                
                for cmd in cmd_list:
                    # 只有在非急停状态下才处理指令
                    if state.mode == "EMERGENCY_STOP": break 
                    
                    cmd_action = cmd.get('action')
                    cmd_type = cmd.get('type')
                    
                    if cmd_type == 'inventory_update':
                        sid = cmd.get('slot_id')
                        sts = cmd.get('status')
                        if sid == 0:
                            for i in range(1, 7): state.inventory[i] = sts
                        elif sid in state.inventory:
                            state.inventory[sid] = sts
                    
                    elif cmd_type == 'sort':
                        target_slot = cmd.get('slot_id')
                        target_color = cmd.get('color', 'any').lower()
                        if target_slot and state.inventory.get(target_slot) == 0:
                            state.current_task = {'slot': target_slot, 'color': target_color}
                            state.mode = "SORTING_TASK"
                        else:
                            state.system_msg = f"Slot {target_slot} Full."

                    elif cmd_action == 'start':
                        if state.mode == "IDLE":
                            if not state.is_at_observe: arm.go_observe(); state.is_at_observe = True
                            state.mode = "AUTO"
                            state.system_msg = "Auto Mode ON"
                    elif cmd_action == 'stop':
                        state.mode = "IDLE"; state.system_msg = "Stopped."
                    elif cmd_action == 'reset': # 软件复位
                        arm.go_observe(); state.is_at_observe = True; state.system_msg = "Reset Done."
                    elif cmd_action == 'clear_all':
                        state.inventory = {i: 0 for i in range(1, 7)}

            # --- 自动化触发逻辑 ---
            trigger_detected = False
            detected_color = "unknown"

            if state.is_at_observe and vision_data and vision_data.get("detected"):
                trigger_detected = True
                detected_color = vision_data.get("color", "unknown").lower()
            
            if state.mode == "AUTO" and trigger_detected:
                target = get_first_empty_slot()
                if target:
                    state.is_at_observe = False 
                    state.mode = "EXECUTING" 
                    t = threading.Thread(target=perform_pick_and_place, args=(arm, target, "EXECUTING", "AUTO"))
                    t.start()
                    time.sleep(0.5)
                else:
                    state.mode = "IDLE"; state.system_msg = "Warehouse Full"

            elif state.mode == "SORTING_TASK" and trigger_detected:
                task = state.current_task
                target_slot = task['slot']
                target_color = task['color']
                is_match = (target_color == 'any' or detected_color == target_color)
                
                if is_match:
                    state.is_at_observe = False
                    state.mode = "SINGLE_TASK"
                    t = threading.Thread(target=perform_pick_and_place, args=(arm, target_slot, "SINGLE_TASK", "IDLE"))
                    t.start()
                    state.current_task = None
                else:
                    # 缓冲逻辑
                    buffer_slot = get_buffer_slot(reserved_slot=target_slot)
                    if buffer_slot:
                        state.is_at_observe = False
                        state.mode = "SINGLE_TASK"
                        t = threading.Thread(target=perform_pick_and_place, args=(arm, buffer_slot, "SINGLE_TASK", "SORTING_TASK"))
                        t.start()
                    else:
                        state.mode = "IDLE"; state.system_msg = "Buffer Full"
                time.sleep(0.5)

            time.sleep(0.03)

    except KeyboardInterrupt:
        print(log_msg("INFO", "System", "User Exit."))
    finally:
        if 'plc' in locals(): plc.close()
        cap.release()
        cv2.destroyAllWindows()
        sys.exit(0)

if __name__ == "__main__":
    main()