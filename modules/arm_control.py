import time
import math
import sys
import os

# 路径处理
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from pymycobot import MyCobot280
    from config import settings
except ImportError:
    print("❌ [Arm] 导入失败，请检查 pymycobot 或 config 文件")
    sys.exit(1)

class ArmController:
    def __init__(self):
        print(">>> [Arm] 初始化机械臂驱动 (固定点位版)...")
        try:
            self.mc = MyCobot280(settings.PORT, settings.BAUD)
            time.sleep(0.5)
            self.mc.power_on()
            time.sleep(1)
            self.move_mode = 1  # 线性移动
            self.speed = 80
            
            self.gripper_open()
            
        except Exception as e:
            print(f"❌ [Arm] 连接失败: {e}")
            self.mc = None

    def gripper_open(self):
        if not self.mc: return
        self.mc.set_gripper_value(100, 70)
        time.sleep(1.0)

    def gripper_close(self):
        if not self.mc: return
        self.mc.set_gripper_value(10, 70)
        time.sleep(1.0)

    # --- 闭环检测 ---
    def wait_until_arrival(self, target_coords, tolerance=15, timeout=15):
        if not self.mc: return
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
        """回观测点 (即抓取最高点)"""
        if not self.mc: return
        print(">>> [Arm] 🚀 正在归位 (Observe Point)...")
        
        target = settings.OBSERVE_COORDS
        self.mc.send_coords(target, self.speed, self.move_mode)
        self.wait_until_arrival(target, tolerance=15)
        print(">>> [Arm] ✅ 已归位")

    def pick(self):
        """
        执行固定点位抓取：
        不再接受参数，完全依照 settings.PICK_DEFAULT_COORDS 执行
        """
        if not self.mc: return
        print(f"🤖 [Arm] 执行标准抓取流程")

        # 1. 读取配置中的固定坐标
        pick_low = settings.PICK_DEFAULT_COORDS
        
        # 2. 计算对应的最高点 (只改Z)
        # 注意：这里直接使用 OBSERVE_COORDS 也可以，因为它们X,Y一样
        pick_high = list(pick_low)
        pick_high[2] = settings.SAFE_Z
        
        # --- 动作序列 ---
        
        # 1. 确保在上方
        print("   1️⃣ 移动到抓取上方")
        self.mc.send_coords(pick_high, self.speed, self.move_mode)
        self.wait_until_arrival(pick_high, tolerance=15)
        
        self.gripper_open()

        # 2. 垂直下抓
        print("   2️⃣ 垂直下抓")
        self.mc.send_coords(pick_low, self.speed, self.move_mode)
        self.wait_until_arrival(pick_low, tolerance=8)

        self.gripper_close()

        # 3. 垂直抬起
        print("   3️⃣ 垂直抬起")
        self.mc.send_coords(pick_high, self.speed, self.move_mode)
        self.wait_until_arrival(pick_high, tolerance=15)

    def place(self, slot_id):
        """
        执行固定点位放置
        """
        if not self.mc: return
        
        target_slot = settings.STORAGE_RACKS.get(slot_id)
        if not target_slot:
            print(f"❌ [Arm] 无效槽位: {slot_id}")
            return

        print(f"🤖 [Arm] 执行放置 -> {slot_id}号位")

        # 解析坐标
        tx, ty, tz = target_slot[0], target_slot[1], target_slot[2]
        t_pose = target_slot[3:]
        
        # 构造最高点
        place_high = [tx, ty, settings.SAFE_Z] + t_pose
        # 构造放置点
        place_low = [tx, ty, tz] + t_pose

        # 1. 移动到上方
        print("   4️⃣ 移动到槽位上方")
        self.mc.send_coords(place_high, self.speed, self.move_mode)
        self.wait_until_arrival(place_high, tolerance=15)

        # 2. 垂直下放
        print("   5️⃣ 垂直下放")
        self.mc.send_coords(place_low, self.speed, self.move_mode)
        self.wait_until_arrival(place_low, tolerance=8)

        self.gripper_open()

        # 3. 垂直抬起
        print("   6️⃣ 垂直抬起")
        self.mc.send_coords(place_high, self.speed, self.move_mode)
        self.wait_until_arrival(place_high, tolerance=15)

        # 4. 任务结束，回观测点
        self.go_observe()