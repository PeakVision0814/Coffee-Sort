# -*- coding: utf-8 -*-
# modules/arm_control.py

import time
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
        
        # 🌟 核心升级：不再是“死等时间”，而是“最大超时时间(Timeout)”
        # 只要机械臂提前到达，哪怕只用了 0.5 秒，代码也会立刻放行！
        # 设置得稍微长一点 (4~5秒) 作为保底，防止遇到意外卡死
        self.fly_timeout = 4.0     
        self.arrival_timeout = 6.0 
        
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

    # ================= 🌟 工业级闭环控制核心 =================
    def wait_for_arrival(self, target_angles, tolerance=2.5, timeout=5.0):
        """
        智能闭环检测 (升级版)
        :param tolerance: 放宽到 2.5 度，适应桌面级机械臂的物理齿轮间隙
        """
        if not self.is_connected: return False

        # 🔥 核心修复 1：发射指令后，强制闭嘴 0.5 秒，让底层单片机有时间分配电流启动电机
        # 绝对不能立马查询，否则容易引发串口冲突导致获取不到数据
        time.sleep(0.5)

        start_time = time.time()
        last_valid_angles = None
        
        while time.time() - start_time < timeout:
            current_angles = self.mc.get_angles()
            
            # 防抖：确保读到的是真实的 6 轴数组
            if isinstance(current_angles, list) and len(current_angles) == 6:
                last_valid_angles = current_angles
                # 计算 6 个关节的绝对误差
                diffs = [abs(c - t) for c, t in zip(current_angles, target_angles)]
                max_error = max(diffs)
                
                # 如果所有关节误差都在容忍度以内，判定为已到达！
                if max_error <= tolerance:
                    return True
            
            # 休息 0.1 秒，保护串口不被查询风暴压垮
            time.sleep(0.1)
            
        # 🔥 核心修复 2：如果还是超时了，把“案发现场”打印出来，让我们看看究竟差在哪！
        if last_valid_angles:
            diffs = [round(abs(c - t), 1) for c, t in zip(last_valid_angles, target_angles)]
            print(f"⚠️ [Arm] 到达检测超时。最大误差: {max(diffs)}度。允许误差: {tolerance}度。")
            # print(f"    -> 目标: {[round(x,1) for x in target_angles]}")
            # print(f"    -> 实际: {[round(x,1) for x in last_valid_angles]}")
        else:
            print("⚠️ [Arm] 到达检测超时：未读取到有效角度数据，串口可能繁忙。")
            
        return False

    def move_to_angles_smart(self, angles, speed, timeout):
        """发送角度并智能等待到达"""
        if self.is_connected:
            self.mc.send_angles(angles, speed)
            self.wait_for_arrival(angles, tolerance=4.2, timeout=timeout)
    # ========================================================

    def go_observe(self):
        """回到抓取最高观测点"""
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
            print("[ARM] 🛑 EMERGENCY STOP COMMAND SENT!")
            self.mc.stop() 

    def pick(self):
        print("[Arm] Sequence: Picking (Smart Closed-Loop)...")
        p = settings.PICK_POSES
        self.gripper_open()
        
        if p.get("mid"): 
            self.move_to_angles_smart(p["mid"], self.fly_speed, self.fly_timeout)
        
        self.move_to_angles_smart(p["grab"], self.speed, self.arrival_timeout)
        
        self.gripper_close()
        # ⚠️ 只有气爪的闭合/张开是物理气动动作(无坐标反馈)，所以保留零点几秒的死等
        time.sleep(0.5) 
        
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
        # 只有这里死等 0.3 秒，让物品完全落下
        time.sleep(0.3) 
        
        if r.get("mid"): 
            self.move_to_angles_smart(r["mid"], self.fly_speed, self.fly_timeout)
            
        self.move_to_angles_smart(r["high"], self.fly_speed, self.fly_timeout)