# -*- coding: utf-8 -*-
# modules/arm_control.py

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
            
            # 3. 🔥 初始状态：松开气爪 (G2=1 为松开/停止)
            self.gripper_open()
            # 🔥 初始状态：PLC 信号置低 (G5=0)
            self.set_plc_signal(False)
            
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

    # --- 🔥 新增：气爪与 PLC 控制 ---
    def gripper_open(self):
        """松开气爪 (G2 高电平)"""
        if self.is_connected:
            # 假设 0 是闭合 (断开继电器)
            self.mc.set_basic_output(settings.GPIO_GRIPPER, 0)
            time.sleep(0.3)

    def gripper_close(self):
        """闭合气爪 (G2 低电平)"""
        if self.is_connected:
            # 假设 0 是张开 (吸合继电器)
            self.mc.set_basic_output(settings.GPIO_GRIPPER, 1)
            time.sleep(0.3)

    def set_plc_signal(self, active: bool):
        """给 PLC 发送完成信号 (G5)"""
        if self.is_connected:
            # active=True 发送高电平(1)，False 发送低电平(0)
            # 具体电平逻辑取决于 PLC 是 PNP 还是 NPN，这里假设高电平有效
            val = 1 if active else 0
            self.mc.set_basic_output(settings.GPIO_PLC_SIGNAL, val)

    # --- 核心工具 ---
    def move_to_angles(self, angles, speed, delay_time):
        if not self.is_connected: return
        try:
            self.mc.send_angles(angles, speed)
            time.sleep(delay_time)
        except Exception as e:
            print(f"[ERROR] [Arm] Move command failed: {e}")

    # --- 业务动作 ---

    def go_observe(self):
        if not self.is_connected: return
        print("[INFO] [Arm] Executing safe reset (observe pose)...")
        try:
            self.mc.power_on()
            time.sleep(0.5)
            target = settings.PICK_POSES["observe"]
            self.move_to_angles(target, self.speed, 2.0) 
            print("[INFO] [Arm] Reset complete.")
        except Exception as e:
            print(f"[ERROR] [Arm] Reset failed: {e}")

    def pick(self):
        """执行抓取流程 (已适配气爪)"""
        if not self.is_connected: return
        print(f"[INFO] [Arm] Sequence START: Pick Operation")

        pose_high = settings.PICK_POSES["observe"] 
        pose_low  = settings.PICK_POSES["grab"]    
        
        # 1. 确保气爪松开
        self.gripper_open()
        
        # 2. 下抓
        self.move_to_angles(pose_low, self.speed, 1.2)
        
        # 3. 闭合气爪 (抓取)
        self.gripper_close()
        time.sleep(0.5) # 等待气压稳定

        # 4. 抬起
        self.move_to_angles(pose_high, self.speed, 1.0)

    def place(self, slot_id):
        """放置到槽位 (已适配气爪 + PLC信号)"""
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

        # 3. 松开气爪 (放置)
        self.gripper_open()
        time.sleep(0.5) 

        # 4. 抬起 (High)
        self.move_to_angles(pose_high, self.speed, 1.0)

        # 5. 🔥 给 PLC 发送完成信号 (脉冲)
        print("[INFO] [Arm] Sending PLC Finish Signal...")
        self.set_plc_signal(True)  # ON
        time.sleep(0.5)            # 保持 0.5 秒
        self.set_plc_signal(False) # OFF

        # 6. 归位
        self.go_observe()
        print(f"[INFO] [Arm] Sequence COMPLETE.")