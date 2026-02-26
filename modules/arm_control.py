# -*- coding: utf-8 -*-
# Copyright (c) 2026 Hangzhou Zhicheng Technology Co., Ltd. All rights reserved.
# 
# This code is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.
# 
# System: Coffee Intelligent Sorting System
# Author: Hangzhou Zhicheng Technology Co., Ltd
# modules/arm_control.py

import time
import math
from config import settings

try:
    from pymycobot import MyCobot280
except ImportError:
    from pymycobot import MyCobot as MyCobot280

class ArmController:
    def __init__(self):
        self.mc = None
        self.is_connected = False
        
        # 速度设置
        self.speed = 50         # 精准下探速度
        self.fly_speed = 80     # 空中飞越速度
        
        self.fly_timeout = 4.0     
        self.arrival_timeout = 6.0 

        self.monitor_g35_estop = False
        
        self._init_robot()

    def _init_robot(self):
        try:
            self.mc = MyCobot280(settings.PORT, settings.BAUD)
            time.sleep(0.5)
            if not self.mc.is_power_on(): self.mc.power_on()
            self.gripper_open()
            self.set_plc_signal(False)
            self.is_connected = True
            print(f"✅ [Arm] 已成功连接真实机械臂于 {settings.PORT}")
        except Exception as e:
            print(f"❌ [Arm] 连接真实机械臂失败: {e}")

    def gripper_open(self):
        if self.is_connected: self.mc.set_basic_output(settings.GPIO_GRIPPER, 0)

    def gripper_close(self):
        if self.is_connected: self.mc.set_basic_output(settings.GPIO_GRIPPER, 1)

    def set_plc_signal(self, active: bool):
        if self.is_connected:
            self.mc.set_basic_output(settings.GPIO_PLC_SIGNAL, 1 if active else 0)

    # ================= 🌟 急停与监控逻辑 =================
    def check_g35_safe(self):
        """
        实时监控 G35 (启动许可信号)：只有明确读到 0（断开）才触发急停。
        加入动态监控开关机制。
        """
        if not self.is_connected: return True
        
        if getattr(self, 'monitor_g35_estop', False) == False:
            return True
            
        # 🔥 修改这里：现在 G35 对应的是 START_BTN！
        val = self.get_input(settings.GPIO_START_BTN)
        
        if val == 0:
            time.sleep(0.02)
            # 🔥 这里也要同步修改
            val2 = self.get_input(settings.GPIO_START_BTN)
            if val2 == 0:    
                return False
        return True

    def safe_sleep(self, duration):
        """带有急停监控的等待函数，用来彻底替代普通的 time.sleep()"""
        start_time = time.time()
        while time.time() - start_time < duration:
            if not self.check_g35_safe():
                self.emergency_stop() # 立即下发硬件急停指令！
                raise RuntimeError("EMERGENCY_STOP") # 抛出异常，切断后续所有代码
            time.sleep(0.05) # 每次只睡 0.05 秒，然后起来检查

    # ================= 🌟 工业级闭环控制核心 =================
    def wait_for_arrival(self, target_angles, tolerance=2.5, timeout=5.0):
        if not self.is_connected: return False

        # 🔥 使用 safe_sleep 替代 time.sleep，即使在这 0.5 秒里也能急停
        self.safe_sleep(0.5)

        start_time = time.time()
        last_valid_angles = None
        
        while time.time() - start_time < timeout:
            # 🔥 核心修改：在死等走位的循环中，随时检查 G35
            if not self.check_g35_safe():
                self.emergency_stop()
                raise RuntimeError("EMERGENCY_STOP")

            current_angles = self.mc.get_angles()
            
            if isinstance(current_angles, list) and len(current_angles) == 6:
                last_valid_angles = current_angles
                diffs = [abs(c - t) for c, t in zip(current_angles, target_angles)]
                max_error = max(diffs)
                if max_error <= tolerance:
                    return True
            
            time.sleep(0.1)
            
        if last_valid_angles:
            diffs = [round(abs(c - t), 1) for c, t in zip(last_valid_angles, target_angles)]
            print(f"⚠️ [Arm] 到达检测超时。最大误差: {max(diffs)}度。允许误差: {tolerance}度。")
        else:
            print("⚠️ [Arm] 到达检测超时：未读取到有效角度数据，串口可能繁忙。")
            
        return False

    def move_to_angles_smart(self, angles, speed, timeout):
        if self.is_connected:
            self.mc.send_angles(angles, speed)
            self.wait_for_arrival(angles, tolerance=4.2, timeout=timeout)

    def go_observe(self):
        """回到抓取最高观测点 (带有极其聪明的智能防撞与防绕路逻辑)"""
        if not self.is_connected: return
        
        try:
            # 1. 获取机械臂目前的 6 轴角度
            current_angles = self.mc.get_angles()
            
            if isinstance(current_angles, list) and len(current_angles) == 6:
                target_observe = settings.PICK_POSES["observe"]
                
                # 2. 🔥 核心修复：先计算离“最终目的地(观测点)”有多远，作为默认的最小距离！
                min_dist = math.sqrt(sum((c - t)**2 for c, t in zip(current_angles, target_observe)))
                closest_waypoint = None  # 如果保持为 None，说明直接回家最近
                closest_name = "Observe Point"
                
                # 3. 遍历 1~6 号槽位，看看有没有比“直接回家”更近的防撞点
                for slot_id in range(1, 7):
                    rack_data = settings.STORAGE_RACKS.get(slot_id)
                    if rack_data and "high" in rack_data and sum(rack_data["high"]) != 0:
                        target_high = rack_data["high"]
                        
                        dist = math.sqrt(sum((c - t)**2 for c, t in zip(current_angles, target_high)))
                        
                        # 如果发现离某个槽位的上方更近（说明现在正深陷在那个槽位附近）
                        if dist < min_dist:
                            min_dist = dist
                            closest_waypoint = target_high
                            closest_name = f"Slot {slot_id} High"
                            
                # 4. 如果找到了比直接回家更近的过渡点，才先飞去那里把手抬高！
                if closest_waypoint:
                    print(f"[Arm] 路径优化：当前深陷 {closest_name} 附近，先垂直退回该安全点...")
                    self.move_to_angles_smart(closest_waypoint, self.fly_speed, self.fly_timeout)
                else:
                    # 如果没有触发上面的 if，说明它发现直接回家就是最短、最安全的路径
                    pass 
                    
        except Exception as e:
            print(f"⚠️ [Arm] 智能寻路计算异常，将直接复位: {e}")
            
        # 5. 最终平移飞回全局最高观测点
        print("[Arm] 正在返回最高观测点...")
        self.move_to_angles_smart(settings.PICK_POSES["observe"], self.fly_speed, self.fly_timeout)

    def get_input(self, pin):
        if self.is_connected:
            return self.mc.get_basic_input(pin)
        return 0

    def is_start_signal_active(self):
        return self.get_input(settings.GPIO_START_BTN) == 1

    def is_reset_signal_active(self):
        return self.get_input(settings.GPIO_RESET_BTN) == 1

    def emergency_stop(self):
        if self.is_connected:
            print("[ARM] 🛑 触发急停！已向主板发送停止指令！")
            self.mc.stop() 

    # ================= 动作序列 =================
    def pick(self):
        print("[Arm] Sequence: Picking (Smart Closed-Loop)...")
        p = settings.PICK_POSES
        self.gripper_open()
        
        if p.get("mid"): 
            self.move_to_angles_smart(p["mid"], self.fly_speed, self.fly_timeout)
        self.move_to_angles_smart(p["grab"], self.speed, self.arrival_timeout)
        
        self.gripper_close()
        # 🔥 替换普通 sleep 为 safe_sleep
        self.safe_sleep(0.5) 
        
        if p.get("mid"): 
            self.move_to_angles_smart(p["mid"], self.fly_speed, self.fly_timeout)
            
        self.move_to_angles_smart(p["observe"], self.fly_speed, self.fly_timeout)

    def place(self, slot_id):
        print(f"[Arm] Sequence: Placing to Slot {slot_id} (Smart Closed-Loop)...")
        r = settings.STORAGE_RACKS.get(slot_id)
        if not r: return

        self.move_to_angles_smart(r["high"], self.fly_speed, self.fly_timeout)
        if r.get("mid"): 
            self.move_to_angles_smart(r["mid"], self.fly_speed, self.fly_timeout)
        self.move_to_angles_smart(r["low"], self.speed, self.arrival_timeout)
        
        self.gripper_open()
        # 🔥 替换普通 sleep 为 safe_sleep
        self.safe_sleep(0.3) 
        
        if r.get("mid"): 
            self.move_to_angles_smart(r["mid"], self.fly_speed, self.fly_timeout)
            
        self.move_to_angles_smart(r["high"], self.fly_speed, self.fly_timeout)