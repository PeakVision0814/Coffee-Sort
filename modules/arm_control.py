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
        self.speed = 60         # 精准速度 (Low点使用)
        self.fly_speed = 100    # 飞越速度 (Mid/High点使用)
        self.fly_time = 0.3     # Mid点短暂停留时间
        self.arrival_time = 1.8 # Low点完全停止并执行气爪的时间
        self._init_robot()

    def _init_robot(self):
        if settings.SIMULATION_MODE: return
        try:
            self.mc = MyCobot280(settings.PORT, settings.BAUD)
            time.sleep(0.5)
            if not self.mc.is_power_on(): self.mc.power_on()
            self.gripper_open()
            self.set_plc_signal(False)
            self.is_connected = True
        except Exception as e:
            print(f"[ERROR] [Arm] Connection failed: {e}")

    def gripper_open(self):
        if self.is_connected: self.mc.set_basic_output(settings.GPIO_GRIPPER, 0)

    def gripper_close(self):
        if self.is_connected: self.mc.set_basic_output(settings.GPIO_GRIPPER, 1)

    def set_plc_signal(self, active: bool):
        if self.is_connected:
            self.mc.set_basic_output(settings.GPIO_PLC_SIGNAL, 1 if active else 0)

    def move_to_angles(self, angles, speed, delay):
        if self.is_connected:
            self.mc.send_angles(angles, speed)
            if delay > 0: time.sleep(delay)

    def go_observe(self):
        """回到抓取最高观测点"""
        self.move_to_angles(settings.PICK_POSES["observe"], self.fly_speed, 1.5)

    def pick(self):
        """抓取逻辑: High -> Mid -> Low -> Grab -> Mid -> High"""
        print("[Arm] Sequence: Picking...")
        p = settings.PICK_POSES
        self.gripper_open()
        
        # 下行
        if p.get("mid"): self.move_to_angles(p["mid"], self.fly_speed, self.fly_time)
        self.move_to_angles(p["grab"], self.speed, self.arrival_time)
        
        # 抓取
        self.gripper_close()
        time.sleep(0.5)
        
        # 上升 (回到High点)
        if p.get("mid"): self.move_to_angles(p["mid"], self.fly_speed, self.fly_time)
        self.move_to_angles(p["observe"], self.fly_speed, self.fly_time)

    def place(self, slot_id):
        """放置逻辑: Slot High -> Mid -> Low -> Release -> Mid -> High"""
        print(f"[Arm] Sequence: Placing to Slot {slot_id}...")
        r = settings.STORAGE_RACKS.get(slot_id)
        if not r: return

        # 移动到槽位上方
        self.move_to_angles(r["high"], self.fly_speed, 1.5)
        
        # 下放
        if r.get("mid"): self.move_to_angles(r["mid"], self.fly_speed, self.fly_time)
        self.move_to_angles(r["low"], self.speed, self.arrival_time)
        
        # 释放
        self.gripper_open()
        time.sleep(0.3)
        
        # 撤离 (回到该槽位的High点)
        if r.get("mid"): self.move_to_angles(r["mid"], self.fly_speed, self.fly_time)
        self.move_to_angles(r["high"], self.fly_speed, 0.5)
        
        # 发送信号并最终归位
        self.set_plc_signal(True)
        time.sleep(0.2)
        self.set_plc_signal(False)