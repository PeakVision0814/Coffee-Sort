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
                time.sleep(0.2)
            
            # 3. 初始状态
            self.gripper_open()
            self.set_plc_signal(False)
            
            # --- 速度策略 ---
            # 精准速度：用于最后接近目标，稍微慢一点点保证准度
            self.speed = 60 
            # 飞越速度：用于中间过渡，全速运行
            self.fly_speed = 100
            
            # --- 延时策略 (关键修改) ---
            # 飞越时间：中间点只停顿一瞬间
            self.fly_time = 0.3
            # 到位时间：目标点必须给足时间让机械臂飞过去 (如果抓不准，调大这个值)
            self.arrival_time = 1.8 
            
            # 4. 测试通讯
            angles = self.mc.get_angles()
            if angles:
                print(f"[INFO] [Arm] Connected. Angles: {angles}")
                self.is_connected = True
                self.mc.set_color(0, 255, 0)
            else:
                print("[ERROR] [Arm] Port opened but read failed.")
                
        except Exception as e:
            print(f"[ERROR] [Arm] Connection failed: {e}")

    # --- 气爪与 PLC ---
    def gripper_open(self):
        if self.is_connected:
            self.mc.set_basic_output(settings.GPIO_GRIPPER, 0)
            time.sleep(0.1)

    def gripper_close(self):
        if self.is_connected:
            self.mc.set_basic_output(settings.GPIO_GRIPPER, 1)
            time.sleep(0.1)

    def set_plc_signal(self, active: bool):
        if self.is_connected:
            val = 1 if active else 0
            self.mc.set_basic_output(settings.GPIO_PLC_SIGNAL, val)

    # --- 核心工具 ---
    def move_to_angles(self, angles, speed, delay_time):
        """发送指令并等待"""
        if not self.is_connected: return
        try:
            self.mc.send_angles(angles, speed)
            if delay_time > 0:
                time.sleep(delay_time)
        except Exception as e:
            print(f"[ERROR] [Arm] Move command failed: {e}")

    # --- 业务动作 (修复版) ---

    def go_observe(self):
        if not self.is_connected: return
        try:
            target = settings.PICK_POSES["observe"]
            # 归位可以快一点
            self.move_to_angles(target, self.fly_speed, 1.5) 
        except Exception as e:
            print(f"[ERROR] Reset failed: {e}")

    def pick(self):
        """执行抓取"""
        if not self.is_connected: return
        print(f"[INFO] [Arm] Action: Pick")

        pose_high = settings.PICK_POSES["observe"]
        pose_mid  = settings.PICK_POSES.get("mid")
        pose_low  = settings.PICK_POSES["grab"]    
        
        self.gripper_open()
        
        # --- 下行阶段 ---
        if pose_mid:
            # High -> Mid: 快速逼近，不停留 (delay=0.3)
            self.move_to_angles(pose_mid, self.fly_speed, self.fly_time)
        
        # Mid -> Low: 🔥 关键修改！必须给足时间 (delay=1.8)
        # 只有机械臂完全到位了，才能执行下一句 gripper_close
        self.move_to_angles(pose_low, self.speed, self.arrival_time)
        
        # --- 抓取 ---
        # 此时机械臂应该已经静止在 Low 点了
        self.gripper_close()
        time.sleep(0.5) # 抓紧等待

        # --- 上行阶段 ---
        if pose_mid:
            # Low -> Mid: 快速离开
            self.move_to_angles(pose_mid, self.fly_speed, self.fly_time)
            
        # Mid -> High: 快速回正
        self.move_to_angles(pose_high, self.fly_speed, self.fly_time)

    def place(self, slot_id):
        """放置"""
        if not self.is_connected: return
        
        rack_data = settings.STORAGE_RACKS.get(slot_id)
        if not rack_data: return

        print(f"[INFO] [Arm] Action: Place -> {slot_id}")
        
        pose_high = rack_data["high"]
        pose_mid  = rack_data.get("mid")
        pose_low  = rack_data["low"]

        # 1. 飞向槽位上方
        self.move_to_angles(pose_high, self.fly_speed, 1.5) 

        # 2. --- 下放阶段 ---
        if pose_mid:
            # High -> Mid: 快速逼近
            self.move_to_angles(pose_mid, self.fly_speed, self.fly_time)
            
        # Mid -> Low: 🔥 关键修改！必须到位 (delay=1.8)
        self.move_to_angles(pose_low, self.speed, self.arrival_time)

        # 3. --- 放下 ---
        # 此时机械臂已经静止在 Low 点
        self.gripper_open()
        time.sleep(0.3) 

        # 4. --- 撤离阶段 ---
        if pose_mid:
            # Low -> Mid: 快速撤离
            self.move_to_angles(pose_mid, self.fly_speed, self.fly_time)
            
        # Mid -> High
        self.move_to_angles(pose_high, self.fly_speed, self.fly_time)

        # 5. PLC 信号
        self.set_plc_signal(True)
        time.sleep(0.2)
        self.set_plc_signal(False)

        # 6. 归位
        self.go_observe()