# -*- coding: utf-8 -*-
# Copyright (c) 2026 Hangzhou Zhicheng Technology Co., Ltd. All rights reserved.
# 
# This code is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.
# 
# System: Coffee Intelligent Sorting System
# Author: Hangzhou Zhicheng Technology Co., Ltd
# modules\arm_control.py

import time
import sys
import os
from config import settings

# 导入驱动
try:
    from pymycobot import MyCobot280
except ImportError:
    from pymycobot import MyCobot as MyCobot280

class ArmController:
    def __init__(self):
        print(f"[INIT] [Arm] Initializing driver on port {settings.PORT}...")
        self.mc = None
        self.is_connected = False

        if settings.SIMULATION_MODE:
            print("[WARN] [Arm] Running in SIMULATION MODE.")
            return

        try:
            # 1. 连接
            self.mc = MyCobot280(settings.PORT, settings.BAUD)
            time.sleep(0.5)
            
            # 2. 上电
            if not self.mc.is_power_on():
                self.mc.power_on()
                time.sleep(0.5)
            
            # 3. 初始状态
            self.mc.set_gripper_value(100, 70) # 张开
            
            # 速度设置
            self.speed = 80
            
            # 4. 测试通讯
            angles = self.mc.get_angles()
            if angles:
                print(f"[INFO] [Arm] Connected successfully. Angles: {angles}")
                self.is_connected = True
                self.mc.set_color(0, 255, 0)
            else:
                print("[ERROR] [Arm] Port opened but read failed.")
                
        except Exception as e:
            print(f"[ERROR] [Arm] Connection failed: {e}")

    # --- 核心工具 ---
    def move_to_angles(self, angles, speed, delay_time):
        """最稳健的移动方式：发送角度 -> 等待"""
        if not self.is_connected: return
        try:
            self.mc.send_angles(angles, speed)
            time.sleep(delay_time)
        except Exception as e:
            print(f"[ERROR] [Arm] Move command failed: {e}")

    # --- 业务动作 ---

    def go_observe(self):
        """前往抓取观测点 (安全复位)"""
        if not self.is_connected: return
        
        print("[INFO] [Arm] Executing safe reset (observe pose)...")
        try:
            # 1. 强制上电 (Torque On)
            self.mc.power_on()
            time.sleep(0.5) 
            
            # 2. 发送归位指令
            target = settings.PICK_POSES["observe"]
            self.move_to_angles(target, self.speed, 2.0) 
            
            print("[INFO] [Arm] Reset complete.")
        except Exception as e:
            print(f"[ERROR] [Arm] Reset failed: {e}")

    def pick(self):
        """执行抓取流程"""
        if not self.is_connected: return
        print(f"[INFO] [Arm] Sequence START: Pick Operation")

        pose_high = settings.PICK_POSES["observe"] 
        pose_low  = settings.PICK_POSES["grab"]    
        
        # 1. 下抓
        # print("   1️⃣ Approach Target") # 可选：保留数字步骤，或改为英文日志
        self.mc.set_gripper_value(100, 70) 
        self.move_to_angles(pose_low, self.speed, 1.2)
        
        # 2. 闭合
        # print("   2️⃣ Close Gripper")
        self.mc.set_gripper_value(10, 70)
        time.sleep(0.8)

        # 3. 抬起
        # print("   3️⃣ Lift Object")
        self.move_to_angles(pose_high, self.speed, 1.0)

    def place(self, slot_id):
        """放置到槽位"""
        if not self.is_connected: return
        
        rack_data = settings.STORAGE_RACKS.get(slot_id)
        if not rack_data:
            print(f"[ERROR] [Arm] Invalid slot ID: {slot_id}")
            return

        print(f"[INFO] [Arm] Sequence START: Place -> Slot {slot_id}")
        
        pose_high = rack_data["high"]
        pose_low  = rack_data["low"]

        # 1. 移动到槽位上方 (High)
        self.move_to_angles(pose_high, self.speed, 2.0) 

        # 2. 下放 (Low)
        self.move_to_angles(pose_low, self.speed, 1.2)

        # 3. 松开
        self.mc.set_gripper_value(100, 70)
        time.sleep(0.5) 

        # 4. 抬起 (High)
        self.move_to_angles(pose_high, self.speed, 1.0)

        # 5. 归位
        self.go_observe()
        print(f"[INFO] [Arm] Sequence COMPLETE.")