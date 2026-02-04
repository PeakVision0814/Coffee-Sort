import time
import math
import sys
import os

# 路径处理
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings

# 根据配置导入驱动
if settings.SIMULATION_MODE:
    from modules.mock_hardware import MockMyCobot as MyCobotDriver
else:
    try:
        from pymycobot import MyCobot280 as MyCobotDriver
    except ImportError:
        print("❌ 无法导入 pymycobot，自动切换到仿真模式")
        settings.SIMULATION_MODE = True
        from modules.mock_hardware import MockMyCobot as MyCobotDriver

class ArmController:
    def __init__(self):
        mode_str = "仿真模式" if settings.SIMULATION_MODE else "真实模式"
        print(f">>> [Arm] 初始化驱动 ({mode_str})...")
        
        try:
            self.mc = MyCobotDriver(settings.PORT, settings.BAUD)
            
            if not settings.SIMULATION_MODE:
                time.sleep(0.5)
                self.mc.power_on()
                time.sleep(1)
            
            self.move_mode = 1
            self.speed = 80     
            self.gripper_open()
            
        except Exception as e:
            print(f"❌ [Arm] 连接失败: {e}")
            self.mc = None

    def gripper_open(self):
        if not self.mc: return
        self.mc.set_gripper_value(100, 70)
        # 仿真模式不需要太长的物理等待
        time.sleep(0.2 if settings.SIMULATION_MODE else 1.0)

    def gripper_close(self):
        if not self.mc: return
        self.mc.set_gripper_value(10, 70)
        time.sleep(0.2 if settings.SIMULATION_MODE else 1.0)

    # --- 闭环检测 ---
    def wait_until_arrival(self, target_coords, tolerance=15, timeout=15):
        if not self.mc: return
        
        # 仿真模式下，MockHardware 会瞬间把 coords 更新，所以这里直接通过
        if settings.SIMULATION_MODE:
            # 稍微模拟一点点延时感
            time.sleep(0.1) 
            return

        start_t = time.time()
        while True:
            if time.time() - start_t > timeout:
                print(" -> ❌ [Arm] 超时跳过")
                break
            curr = self.mc.get_coords()
            if not curr or len(curr) < 6:
                time.sleep(0.1)
                continue
            dx = curr[0] - target_coords[0]
            dy = curr[1] - target_coords[1]
            dz = curr[2] - target_coords[2]
            dist = math.sqrt(dx**2 + dy**2 + dz**2)
            if dist < tolerance:
                break
            time.sleep(0.1)

    # --- 业务动作 ---

    def go_observe(self):
        if not self.mc: return
        print(">>> [Arm] 🚀 正在归位 (Observe Point)...")
        target = settings.OBSERVE_COORDS
        self.mc.send_coords(target, self.speed, self.move_mode)
        self.wait_until_arrival(target, tolerance=15)
        print(">>> [Arm] ✅ 已归位")

    def pick(self):
        if not self.mc: return
        print(f"🤖 [Arm] 执行标准抓取流程")
        pick_low = settings.PICK_DEFAULT_COORDS
        pick_high = list(pick_low)
        pick_high[2] = settings.SAFE_Z
        
        print("   1️⃣ 移动到抓取上方")
        self.mc.send_coords(pick_high, self.speed, self.move_mode)
        self.wait_until_arrival(pick_high, tolerance=15)
        
        self.gripper_open()

        print("   2️⃣ 垂直下抓")
        self.mc.send_coords(pick_low, self.speed, self.move_mode)
        self.wait_until_arrival(pick_low, tolerance=8)

        self.gripper_close()

        print("   3️⃣ 垂直抬起")
        self.mc.send_coords(pick_high, self.speed, self.move_mode)
        self.wait_until_arrival(pick_high, tolerance=15)

    def place(self, slot_id):
        if not self.mc: return
        
        target_slot = settings.STORAGE_RACKS.get(slot_id)
        if not target_slot:
            print(f"❌ [Arm] 无效槽位: {slot_id}")
            return

        print(f"🤖 [Arm] 执行放置 -> {slot_id}号位")
        tx, ty, tz = target_slot[0], target_slot[1], target_slot[2]
        t_pose = target_slot[3:]
        
        place_high = [tx, ty, settings.SAFE_Z] + t_pose
        place_low = [tx, ty, tz] + t_pose

        print("   4️⃣ 移动到槽位上方")
        self.mc.send_coords(place_high, self.speed, self.move_mode)
        self.wait_until_arrival(place_high, tolerance=15)

        print("   5️⃣ 垂直下放")
        self.mc.send_coords(place_low, self.speed, self.move_mode)
        self.wait_until_arrival(place_low, tolerance=8)

        self.gripper_open()

        print("   6️⃣ 垂直抬起")
        self.mc.send_coords(place_high, self.speed, self.move_mode)
        self.wait_until_arrival(place_high, tolerance=15)

        self.go_observe()