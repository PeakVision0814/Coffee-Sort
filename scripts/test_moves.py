import sys
import os
import time

# --- 关键修复：把项目根目录加入到 Python 搜索路径中 ---
# 这一行代码的作用是：找到当前文件的上一级目录，并把它加入系统路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.arm_control import ArmController
from config import settings


def test():
    print(">>> 开始动作参数验证...")
    # 初始化
    arm = ArmController()
    if not arm.mc: 
        print("❌ 机械臂未连接，无法测试")
        return

    # 1. 去观测点
    print(f"1. 前往观测点 (Z={settings.OBSERVE_Z})...")
    arm.go_observe()
    print("✅ 已到达观测点。请观察：")
    print("   - 摄像头是否垂直向下？")
    print("   - 高度是否合适？")
    time.sleep(2)

    # 2. 模拟去 A 仓放东西
    print("2. 测试去 A 仓放料...")
    # 这里只是为了测试移动，所以动作要慢一点
    arm.place("A")
    
    # 3. 回家
    print("3. 测试完成，回原点...")
    arm.go_home()
    print("🎉 验证完成！如果没有撞机，动作流畅，就可以跑 main.py 了")

if __name__ == "__main__":
    test()