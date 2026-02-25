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
        # 模式包括: IDLE, AUTO, SORTING_TASK, EXECUTING, SINGLE_TASK
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
    """纯净版搬运流程：加入 PLC 业务握手"""
    try:
        state.is_at_observe = False
        state.mode = active_mode
        
        # --- 1. 抓取 ---
        arm.pick()
        
        if state.mode == "IDLE" and restore_mode != "IDLE":
            print(log_msg("WARN", "System", "Interrupt detected."))
            restore_mode = "IDLE"

        # --- 2. 放置 ---
        arm.place(target_slot)
        
        # --- 3. 🔥 动作完美完成，向 PLC 发送 G5 完成信号 ---
        print(log_msg("INFO", "System", "Sending Task Complete Signal (G5) to PLC..."))
        arm.set_plc_signal(True)
        time.sleep(0.5)  # 保持高电平 0.5 秒，确保 PLC 的扫描周期能稳定捕捉到这个脉冲
        arm.set_plc_signal(False)
        
        # --- 4. 更新系统状态 ---
        state.inventory[target_slot] = 1
        state.system_msg = get_standard_success_msg(target_slot)
        print(log_msg("INFO", "System", f"Slot {target_slot} mission complete."))

    except Exception as e:
        # 如果上方任何一步（视觉、控制、通信）报错，绝对不会走到发信号这一步
        state.system_msg = f"❌ Error: {e}"
        print(log_msg("ERROR", "System", f"Process Stopped: {e}"))
        try: arm.go_observe()
        except: pass
        restore_mode = "IDLE" 
    
    finally:
        print(log_msg("INFO", "System", "Returning to Observe Point..."))
        arm.go_observe() 
        state.is_at_observe = True
        
        if state.mode == active_mode:
            state.mode = restore_mode

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
    
    print(log_msg("INFO", "System", "Connecting to PLC (Ethernet) for Inventory Only..."))
    plc = PLCClient(ip='192.168.0.10')
    
    # 🔥 彻底移除 MockCamera，强制使用真实的物理摄像头
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # 纯净启动逻辑: 直接让机械臂归位并就绪
    if arm.mc:
        print(log_msg("INFO", "System", "Initial Homing..."))
        arm.go_observe()
        state.is_at_observe = True

    web_thread = threading.Thread(target=web_server.start_flask, args=(state, ai), daemon=True)
    web_thread.start()
    
    print(log_msg("INFO", "Web", "Console at http://127.0.0.1:5000"))
    time.sleep(1.0)
    webbrowser.open("http://127.0.0.1:5000")

    try:
        while True:
            # ==========================================
            # 保留的 PLC 交互：单纯读取物理库存
            # ==========================================
            real_inventory = plc.get_slots_status()
            if real_inventory: 
                state.inventory = real_inventory

            # --- 心跳检测 ---
            if state.mode != "IDLE" and (time.time() - state.last_heartbeat > 5.0):
                print(log_msg("WARN", "System", "Heartbeat lost. Forcing IDLE mode."))
                state.mode = "IDLE"
            
            # --- 🔥 新增：满载全局守护监控 (Watchdog) ---
            # 只要是 AUTO 模式下，实时检查 1~6 号槽位是否全不为 0 (即全满)
            if state.mode == "AUTO":
                if all(state.inventory.get(i, 0) != 0 for i in range(1, 7)):
                    print(log_msg("WARN", "System", "Warehouse is FULL! Auto-switching to IDLE mode."))
                    state.mode = "IDLE"
                    state.system_msg = "Warehouse Full. Auto Stopped."

            # --- 视觉处理 ---
            ret, frame = cap.read()
            if not ret: time.sleep(0.1); continue
            processed_frame, vision_data = vision.process_frame(frame)
            web_server.update_frame(processed_frame)

            # --- AI 指令 ---
            if state.pending_ai_cmd:
                cmd_list = state.pending_ai_cmd
                state.pending_ai_cmd = None 
                
                for cmd in cmd_list:
                    cmd_action = cmd.get('action')
                    cmd_type = cmd.get('type')

                    if cmd_type == 'sort':
                        target_slot = cmd.get('slot_id')
                        target_color = cmd.get('color', 'any').lower()
                        if target_slot and state.inventory.get(target_slot) == 0:
                            state.current_task = {'slot': target_slot, 'color': target_color}
                            state.mode = "SORTING_TASK"
                        else:
                            state.system_msg = f"Slot {target_slot} Full."

                    elif cmd_action == 'start':
                        # 点击开始前，如果已经满了就直接拒绝进入 AUTO，并给出提示
                        if all(state.inventory.get(i, 0) != 0 for i in range(1, 7)):
                            state.system_msg = "Cannot start: Warehouse Full."
                            print(log_msg("WARN", "System", "Start rejected: Warehouse is completely full."))
                        elif state.mode == "IDLE":
                            if not state.is_at_observe: arm.go_observe(); state.is_at_observe = True
                            state.mode = "AUTO"
                            state.system_msg = "Auto Mode ON"
                    elif cmd_action == 'stop':
                        state.mode = "IDLE"; state.system_msg = "Stopped."
                    elif cmd_action == 'reset': 
                        arm.go_observe(); state.is_at_observe = True; state.system_msg = "Reset Done."

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
                    # 这个兜底其实很难触发了，因为上面满载监控会提前拦截，保留作双重保险
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