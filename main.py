# -*- coding: utf-8 -*-
# Copyright (c) 2026 Hangzhou Zhicheng Technology Co., Ltd. All rights reserved.
# 
# This code is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.
# 
# System: Coffee Intelligent Sorting System
# Author: Hangzhou Zhicheng Technology Co., Ltd
# main.py

import cv2
import time
import threading
import sys
import os
import webbrowser
import random 
import logging
from logging.handlers import RotatingFileHandler

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

# ==========================================
# 📝 日志系统配置 (Log Rotation)
# ==========================================
LOG_FILE_PATH = os.path.join("logs", "system.log")

# 确保 logs 文件夹存在
if not os.path.exists("logs"):
    os.makedirs("logs")

# 配置 Logger
logger = logging.getLogger("CoffeeSystem")
logger.setLevel(logging.INFO)

# 1. 文件处理器 (支持轮转：最大 2MB，保留 5 个备份)
file_handler = RotatingFileHandler(
    LOG_FILE_PATH, maxBytes=2*1024*1024, backupCount=5, encoding='utf-8'
)
# 设置文件中的日志格式 (去掉颜色代码，只留纯文本)
file_formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s] %(message)s', datefmt='%H:%M:%S')
file_handler.setFormatter(file_formatter)

# 2. 避免重复添加 Handler
if not logger.handlers:
    logger.addHandler(file_handler)

def log_msg(level, module, message):
    """
    1. 生成带颜色的字符串供控制台打印 (保持原有逻辑)
    2. 将纯净日志写入文件 (新增逻辑)
    """
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    
    # --- 写入文件 (使用 logging 模块) ---
    # 我们把 module 放在 extra 里，或者直接拼接到 msg
    log_content = f"[{module}] {message}"
    if level == "INFO": logger.info(log_content)
    elif level == "WARN": logger.warning(log_content)
    elif level == "ERROR": logger.error(log_content)
    
    # --- 返回控制台字符串 ---
    return f"[{timestamp}] {level} [{module}] {message}"

# 标准化成功消息库
SUCCESS_PHRASES = [
    "Task completed. Item placed in Slot {}.",
    "Operation successful. Slot {} occupied.",
    "Sort execution finished -> Slot {}.",
    "Item stored in Slot {}. Returning to IDLE."
]

def get_standard_success_msg(slot_id):
    phrase = random.choice(SUCCESS_PHRASES).format(slot_id)
    return phrase 

def perform_pick_and_place(arm, target_slot, active_mode="SINGLE_TASK", restore_mode="IDLE"):
    try:
        state.mode = active_mode
        arm.pick()
        
        if state.mode == "IDLE" and restore_mode != "IDLE":
            print(log_msg("WARN", "System", "Interrupt detected during pick operation."))
            restore_mode = "IDLE"

        arm.place(target_slot)
        state.inventory[target_slot] = 1
        
        # 任务完成后，设置系统消息
        state.system_msg = get_standard_success_msg(target_slot)
        print(log_msg("INFO", "System", f"Slot {target_slot} status updated: FULL"))

    except Exception as e:
        state.system_msg = f"❌ Error: {e}"
        print(log_msg("ERROR", "System", f"Pick & Place failed: {e}"))
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

    print(log_msg("INFO", "Web", "Console started at http://127.0.0.1:5000"))
    time.sleep(1.0)
    webbrowser.open("http://127.0.0.1:5000")

    try:
        while True:
            # 心跳检测
            if state.mode != "IDLE" and (time.time() - state.last_heartbeat > 5.0):
                print(log_msg("WARN", "System", "Heartbeat lost. Forcing IDLE mode."))
                state.mode = "IDLE"
                state.current_task = None
                state.system_msg = "⚠️ Connection lost. System paused."

            ret, frame = cap.read()
            if not ret: 
                time.sleep(0.1)
                continue
            
            processed_frame, vision_data = vision.process_frame(frame)
            
            if state.pending_ai_cmd:
                cmd = state.pending_ai_cmd
                cmd_action = cmd.get('action')
                cmd_type = cmd.get('type')
                
                print(log_msg("INFO", "Main", f"Received CMD: {cmd}"))

                if cmd_action == 'start':
                    if state.mode == "IDLE":
                        state.system_msg = "Initializing arm..."
                        arm.go_observe()
                        
                        state.mode = "AUTO"
                        state.current_task = None 
                        state.system_msg = "Auto-sorting pipeline started."
                        print(log_msg("INFO", "System", "Mode switched to AUTO"))
                        
                elif cmd_action == 'stop':
                    state.mode = "IDLE"
                    state.current_task = None
                    state.system_msg = "System stopped by user."
                    print(log_msg("INFO", "System", "Mode switched to IDLE"))
                    
                elif cmd_action == 'reset':
                    if state.mode in ["IDLE"]:
                        arm.go_observe()
                        state.system_msg = "Arm reset completed."
                    else:
                        state.system_msg = "⚠️ Cannot reset while busy."
                        
                elif cmd_action == 'clear_all':
                    if state.mode in ["IDLE"]:
                        state.inventory = {i: 0 for i in range(1, 7)}
                        state.system_msg = "Inventory cleared."
                        print(log_msg("INFO", "System", "Inventory reset to 0"))
                    else:
                        state.system_msg = "⚠️ Cannot clear inventory while busy."
                        
                elif cmd_action == 'scan':
                    report = [f"Slot{i}:{'FULL' if state.inventory[i] else 'EMPTY'}" for i in range(1,7)]
                    state.system_msg = " | ".join(report)
                    
                elif cmd_type == 'inventory_update':
                    sid = cmd.get('slot_id')
                    sts = cmd.get('status') # 0 代表空，1 代表满
                    
                    # 🔥 新增逻辑：处理 "所有" (slot_id = 0)
                    if sid == 0:
                        # 循环更新所有槽位
                        for i in range(1, 7):
                            state.inventory[i] = sts
                        
                        status_str = "FULL" if sts == 1 else "EMPTY"
                        msg = f"Manual override: ALL SLOTS set to {status_str}."
                        state.system_msg = msg
                        print(log_msg("INFO", "System", msg))
                        
                    # 原有逻辑：处理单个槽位
                    elif sid in state.inventory:
                        state.inventory[sid] = sts
                        status_str = "FULL" if sts == 1 else "EMPTY"
                        state.system_msg = f"Manual update: Slot {sid} -> {status_str}."
                        print(log_msg("INFO", "System", f"Manual update: Slot {sid} -> {status_str}"))
                        
                elif cmd_type == 'sort':
                    target_slot = cmd.get('slot_id')
                    target_color = cmd.get('color', 'any').lower()
                    
                    if target_slot and 1 <= target_slot <= 6:
                        if state.inventory[target_slot] == 1:
                            err_msg = f"⚠️ Operation denied: Slot {target_slot} is FULL."
                            print(log_msg("WARN", "System", err_msg))
                            state.system_msg = err_msg
                        else:
                            state.current_task = {'slot': target_slot, 'color': target_color}
                            state.mode = "SORTING_TASK"
                            print(log_msg("INFO", "Task", f"Target locked: {target_color} -> Slot {target_slot}"))
                    else:
                        state.system_msg = "⚠️ Invalid slot ID."

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
                    state.system_msg = "⚠️ Warehouse FULL. Auto-stop."
                    print(log_msg("WARN", "System", "All slots full. Stopping pipeline."))

            elif state.mode == "SORTING_TASK" and (is_detected or fake_detect):
                task = state.current_task
                target_slot = task['slot']
                target_color = task['color']

                is_match = False
                if target_color == 'any': is_match = True
                elif detected_color == target_color: is_match = True
                
                if is_match:
                    print(log_msg("INFO", "Vision", f"Target match ({detected_color}). Executing sort."))
                    state.mode = "SINGLE_TASK"
                    t = threading.Thread(target=perform_pick_and_place, args=(arm, target_slot, "SINGLE_TASK", "IDLE"))
                    t.start()
                    state.current_task = None
                else:
                    # 缓冲逻辑保持不变，添加日志
                    buffer_slot = get_buffer_slot(reserved_slot=target_slot)
                    if buffer_slot:
                        state.system_msg = f"Moving obstruction ({detected_color})..."
                        state.mode = "SINGLE_TASK"
                        t = threading.Thread(target=perform_pick_and_place, args=(arm, buffer_slot, "SINGLE_TASK", "SORTING_TASK"))
                        t.start()
                        print(log_msg("INFO", "System", f"Buffering {detected_color} item to Slot {buffer_slot}"))
                    else:
                        state.mode = "IDLE"
                        state.system_msg = "❌ Buffer full. Task aborted."
                        state.current_task = None
                        print(log_msg("ERROR", "System", "Buffer overflow. Cannot clear path."))
                time.sleep(0.5)
            time.sleep(0.03)

    except KeyboardInterrupt: pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        sys.exit(0)

if __name__ == "__main__":
    main()