import cv2
import time
import sys
import os
import math
import numpy as np

# 路径处理
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from pymycobot import MyCobot280
    from config import settings
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)

class AutoTestController:
    def __init__(self):
        print(">>> 初始化全自动测试控制器...")
        try:
            self.mc = MyCobot280(settings.PORT, settings.BAUD)
            time.sleep(0.5)
            self.mc.power_on()
            self.move_mode = 1 # 线性移动 (必须是1，保证走直线)
            self.speed = 40    # 速度适中
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            sys.exit(1)

    def gripper_open(self):
        print("      🔓 张开夹爪")
        self.mc.set_gripper_value(100, 70)
        time.sleep(1.0)

    def gripper_close(self):
        print("      🔒 闭合夹爪")
        self.mc.set_gripper_value(10, 70)
        time.sleep(1.0)

    # --- 闭环检测 (复用之前的稳定版本) ---
    def wait_until_arrival(self, target_coords, tolerance=15, timeout=15):
        start_t = time.time()
        # print(f"      ⏳ 目标Z={target_coords[2]:.1f}...", end="")
        last_print = 0
        
        while True:
            # 超时保护
            if time.time() - start_t > timeout:
                print(" -> ❌ 动作超时 (跳过)")
                break

            curr = self.mc.get_coords()
            if not curr or len(curr) < 6:
                time.sleep(0.1)
                continue

            # 计算欧氏距离
            dist = math.sqrt(sum([(curr[i]-target_coords[i])**2 for i in range(3)]))

            # if time.time() - last_print > 1.0:
            #     print(f".{int(dist)}", end="", flush=True)
            #     last_print = time.time()

            if dist < tolerance:
                # print(f" -> ✅ 到位")
                break
            time.sleep(0.1)

    # --- 核心动作逻辑 ---

    def go_observe(self):
        """回到观测点 (即抓取最高点)"""
        print("\n>>> 🚀 正在复位/回观测点...")
        target = settings.OBSERVE_COORDS
        self.mc.send_coords(target, self.speed, self.move_mode)
        self.wait_until_arrival(target, tolerance=15)
        print(">>> ✅ 已就绪")

    def run_full_cycle(self, slot_id):
        """
        一键执行全套动作：抓取 -> 搬运 -> 放置 -> 归位
        """
        print(f"\n==================================")
        print(f"🎬 开始执行 {slot_id} 号位 自动搬运任务")
        print(f"==================================")

        # === 阶段 1: 抓取流程 ===
        
        # 1.1 确保在抓取最高点
        pick_high = settings.OBSERVE_COORDS # 观测点就是抓取最高点
        print("1️⃣ [Pick] 移动到抓取上方")
        self.mc.send_coords(pick_high, self.speed, self.move_mode)
        self.wait_until_arrival(pick_high, tolerance=15)
        
        self.gripper_open()

        # 1.2 垂直下抓
        pick_low = settings.PICK_DEFAULT_COORDS
        print(f"2️⃣ [Pick] 垂直下抓 (Z={pick_low[2]})")
        self.mc.send_coords(pick_low, self.speed, self.move_mode)
        self.wait_until_arrival(pick_low, tolerance=8) # 精度要求高

        self.gripper_close()

        # 1.3 垂直抬起
        print(f"3️⃣ [Pick] 垂直抬起 (Z={pick_high[2]})")
        self.mc.send_coords(pick_high, self.speed, self.move_mode)
        self.wait_until_arrival(pick_high, tolerance=15)


        # === 阶段 2: 放置流程 ===
        
        target_slot = settings.STORAGE_RACKS.get(slot_id)
        if not target_slot:
            print("❌ 槽位数据错误")
            return

        tx, ty, tz = target_slot[0], target_slot[1], target_slot[2]
        t_pose = target_slot[3:]
        
        # 构造放置最高点 (强制垂直)
        place_high = [tx, ty, settings.SAFE_Z] + t_pose
        
        # 2.1 水平移动到槽位上方
        print(f"4️⃣ [Place] 移动到 {slot_id}号 上方")
        self.mc.send_coords(place_high, self.speed, self.move_mode)
        self.wait_until_arrival(place_high, tolerance=15)

        # 2.2 垂直下放
        print(f"5️⃣ [Place] 垂直下放 (Z={tz})")
        # 构造实际下放点
        place_low = [tx, ty, tz] + t_pose
        self.mc.send_coords(place_low, self.speed, self.move_mode)
        self.wait_until_arrival(place_low, tolerance=8)

        self.gripper_open()

        # 2.3 垂直抬起
        print(f"6️⃣ [Place] 垂直抬起 (Z={settings.SAFE_Z})")
        self.mc.send_coords(place_high, self.speed, self.move_mode)
        self.wait_until_arrival(place_high, tolerance=15)

        # === 阶段 3: 归位 ===
        print("7️⃣ 任务完成，回观测点")
        self.go_observe()


def main():
    arm = AutoTestController()
    
    # 简单的控制面板
    import numpy as np
    img = np.zeros((300, 600, 3), dtype='uint8')
    cv2.namedWindow("Auto Test Panel")
    cv2.putText(img, "Press 'P' to Reset/Observe", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(img, "Press '1-6' to Auto Run", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.putText(img, "Press 'Q' to Quit", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.imshow("Auto Test Panel", img)

    # 启动时先回观测点
    arm.go_observe()

    while True:
        key = cv2.waitKey(100) & 0xFF
        if key == ord('q'): break
        
        # P: 仅回观测点
        elif key == ord('p'):
            arm.go_observe()
            
        # 1-6: 自动执行全套逻辑
        elif ord('1') <= key <= ord('6'):
            slot_id = key - ord('0')
            arm.run_full_cycle(slot_id)

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()