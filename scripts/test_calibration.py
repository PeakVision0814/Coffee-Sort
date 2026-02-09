import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
# 强制使用 v3.4 的控制逻辑
from modules.arm_control import ArmController 

def main():
    print("🚀 开始点位巡检测试...")
    arm = ArmController()
    
    if not arm.mc:
        print("❌ 连接失败，终止测试")
        return

    # 1. 测试观测点
    print("\n>>> 1. 前往观测点 (Observe)...")
    arm.go_observe()
    time.sleep(1)

    # 2. 测试抓取动作 (假抓)
    print("\n>>> 2. 测试抓取点 (Pick)...")
    print("   (请确保抓取区有盒子，或者没有障碍物)")
    arm.pick() # 这会调用 settings.PICK_DEFAULT_COORDS
    
    # 3. 测试所有槽位
    print("\n>>> 3. 测试放置槽位 (1-6)...")
    for i in range(1, 7):
        input(f"按 Enter 键测试前往 -> {i}号槽位...")
        arm.place(i) # 这会去 settings.STORAGE_RACKS[i] 然后自动归位
        print(f"✅ {i}号位测试完成")

    print("\n✨ 所有点位巡检完成！")

if __name__ == "__main__":
    main()