import cv2
import time
import sys
import os
import math

# 路径处理
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from pymycobot import MyCobot280
    from config import settings
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)

class InteractiveController:
    def __init__(self):
        print(">>> 初始化控制器 (观测点修正版)...")
        try:
            self.mc = MyCobot280(settings.PORT, settings.BAUD)
            time.sleep(0.5)
            self.mc.power_on()
            self.move_mode = 1 # 线性移动
            self.speed = 40    
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            sys.exit(1)
        
        self.state = "IDLE" 
        self.current_slot = None

    def gripper_open(self):
        self.mc.set_gripper_value(100, 70)
        time.sleep(1.0)

    def gripper_close(self):
        self.mc.set_gripper_value(10, 70)
        time.sleep(1.0)

    # --- 🔥 修正：观测点逻辑 ---
    def go_observe(self):
        """回到观测点 (即抓取最高点)"""
        print("\n>>> 🚀 回观测点 (Pick High)...")
        # 使用坐标控制，而不是角度
        target = settings.OBSERVE_COORDS
        
        self.mc.send_coords(target, self.speed, self.move_mode)
        # 同样使用闭环检测，防止归位时还没到就开始下一次识别
        self.wait_until_arrival(target, tolerance=15)
        
        self.state = "IDLE"
        print(">>> ✅ 已归位")

    # --- 闭环检测 ---
    def wait_until_arrival(self, target_coords, tolerance=15, timeout=15):
        start_t = time.time()
        print(f"      ⏳ 目标Z={target_coords[2]:.1f}...", end="")
        last_print = 0
        
        while True:
            if time.time() - start_t > timeout:
                print(" -> ❌ 超时(跳过)")
                break

            curr = self.mc.get_coords()
            if not curr or len(curr) < 6:
                time.sleep(0.1)
                continue

            dist = math.sqrt(sum([(curr[i]-target_coords[i])**2 for i in range(3)]))

            if time.time() - last_print > 1.0:
                print(f".{int(dist)}", end="", flush=True)
                last_print = time.time()

            if dist < tolerance:
                print(f" -> ✅ 到位({dist:.1f}mm)")
                break
            time.sleep(0.1)

    # --- 动作逻辑 ---

    def move_to_pick_ready(self):
        """移动到抓取点正上方 (测试用)"""
        # 这里演示移动到 settings 里的默认抓取点上方
        # 实际逻辑和 go_observe 其实是一样的，因为观测点=抓取最高点
        # 但为了保留逻辑完整性，我们还是写出来
        target = settings.PICK_DEFAULT_COORDS
        tx, ty = target[0], target[1]
        t_pose = target[3:]
        
        target_high = [tx, ty, settings.SAFE_Z] + t_pose
        
        print(f"\n1️⃣ [Pick] 移动到抓取上方 (Z={settings.SAFE_Z})")
        self.mc.send_coords(target_high, self.speed, self.move_mode)
        self.wait_until_arrival(target_high, tolerance=15)
        
        self.state = "PICK_READY"
        print(">>> ✅ 就绪！按 P 下抓")

    def execute_pick(self):
        target = settings.PICK_DEFAULT_COORDS
        tx, ty, tz = target[0], target[1], target[2]
        t_pose = target[3:]
        
        target_high = [tx, ty, settings.SAFE_Z] + t_pose

        self.gripper_open()

        print(f"\n2️⃣ [Pick] 垂直下抓 (Z={tz})")
        self.mc.send_coords(target, self.speed, self.move_mode)
        self.wait_until_arrival(target, tolerance=8)
        
        self.gripper_close()

        print(f"3️⃣ [Pick] 垂直抬起 (Z={settings.SAFE_Z})")
        self.mc.send_coords(target_high, self.speed, self.move_mode)
        self.wait_until_arrival(target_high, tolerance=15)

        self.state = "HOLDING"
        print(">>> ✅ 已抓取！按 1-6 去放置")

    def move_to_place_ready(self, slot_id):
        target = settings.STORAGE_RACKS.get(slot_id)
        if not target: return

        tx, ty = target[0], target[1]
        t_pose = target[3:]
        
        target_high = [tx, ty, settings.SAFE_Z] + t_pose
        
        print(f"\n1️⃣ [Place] 移动到 {slot_id}号 上方 (Z={settings.SAFE_Z})")
        self.mc.send_coords(target_high, self.speed, self.move_mode)
        self.wait_until_arrival(target_high, tolerance=15)
        
        self.current_slot = slot_id
        self.state = "PLACE_READY"
        print(f">>> ✅ 就绪！再按 {slot_id} 下放")

    def execute_place(self):
        if not self.current_slot: return
        
        target = settings.STORAGE_RACKS.get(self.current_slot)
        tx, ty, tz = target[0], target[1], target[2]
        t_pose = target[3:]
        
        target_high = [tx, ty, settings.SAFE_Z] + t_pose

        print(f"\n2️⃣ [Place] 垂直下放 (Z={tz})")
        self.mc.send_coords(target, self.speed, self.move_mode)
        self.wait_until_arrival(target, tolerance=8)
        
        self.gripper_open()

        print(f"3️⃣ [Place] 垂直抬起 (Z={settings.SAFE_Z})")
        self.mc.send_coords(target_high, self.speed, self.move_mode)
        self.wait_until_arrival(target_high, tolerance=15)

        print(">>> ✅ 放置完成！回观测点")
        self.go_observe()

def main():
    arm = InteractiveController()
    
    import numpy as np
    img = np.zeros((300, 600, 3), dtype='uint8')
    cv2.namedWindow("Control Panel")
    cv2.putText(img, "Press 'P' to Pick Test", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(img, "Press '1-6' to Place", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(img, "Press 'Q' to Quit", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.imshow("Control Panel", img)

    arm.go_observe()

    while True:
        key = cv2.waitKey(100) & 0xFF
        if key == ord('q'): break
        elif key == ord('p'):
            if arm.state == "IDLE": arm.move_to_pick_ready()
            elif arm.state == "PICK_READY": arm.execute_pick()
        elif ord('1') <= key <= ord('6'):
            slot_id = key - ord('0')
            if arm.state == "HOLDING": arm.move_to_place_ready(slot_id)
            elif arm.state == "PLACE_READY" and arm.current_slot == slot_id: arm.execute_place()

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()