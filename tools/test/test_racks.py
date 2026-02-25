# scripts/test_racks.py
import sys
import os
import time

# 路径黑魔法
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.arm_control import ArmController
from config import settings

def main():
    arm = ArmController()
    if not arm.mc: return
    
    print("WARNING: 机械臂即将依次访问 1-6 号槽位！")
    print("请确保周围没有障碍物！")
    input("按回车键开始测试...")
    
    arm.go_observe()
    
    for i in range(1, 7):
        print(f"Testing Slot {i}...")
        arm.place(i) # 这会执行全套动作：转腰 -> 移动 -> 下降 -> 抬起
        time.sleep(1)
        
    print("所有槽位测试完成！")
    arm.go_home()

if __name__ == "__main__":
    main()