# -*- coding: utf-8 -*-
# tests/test_all_racks.py
import sys
import os
import time

# 将项目根目录加入环境变量
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from modules.arm_control import ArmController
from config import settings

# --- 无阻塞监听空格键 ---
try:
    import msvcrt
    def wait_for_space(prompt_msg):
        print(f"\n👉 {prompt_msg} (按空格键继续，按 Q 终止测试)")
        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key == b' ':
                    print("▶️ 收到指令，执行中...")
                    return True
                elif key.lower() == b'q':
                    print("\n⏹️ 收到终止指令，退出测试。")
                    return False
            time.sleep(0.05)
except ImportError:
    def wait_for_space(prompt_msg):
        res = input(f"\n👉 {prompt_msg} (按回车键继续，输入 q 退出): ")
        return res.lower() != 'q'

def run_full_test():
    print("\n" + "★"*50)
    print("🤖 智能分拣系统 - 1~6号槽位全流程连贯质检工具")
    print("★"*50)

    # 1. 初始化机械臂
    arm = ArmController()
    if not arm.is_connected:
        print("❌ 机械臂连接失败，请检查连线或端口配置！")
        return

    try:
        print("\n[系统初始化] 机械臂正在前往最高观测点 (Observe)...")
        arm.go_observe()
        time.sleep(1)

        # 2. 循环遍历 1 到 6 号槽位
        for slot_id in range(1, 7):
            print(f"\n" + "="*40)
            print(f"🎯 准备测试: 搬运至 【 {slot_id} 号槽位 】")
            print("="*40)

            # 检查该槽位是否已经标定 (防呆)
            rack_data = settings.STORAGE_RACKS.get(slot_id)
            if not rack_data or sum(rack_data["low"]) == 0:
                print(f"⚠️ 跳过 {slot_id} 号槽位：检测到该槽位尚未标定有效坐标。")
                continue

            # 3. 等待用户放好盒子并按下空格
            if not wait_for_space(f"请在【抓取区】放好待测盒子，然后按【空格键】"):
                break # 用户按了 Q 键提前终止

            # 4. 执行完整的抓放流水线
            print(f"\n🔄 正在执行抓取...")
            arm.pick()
            
            print(f"🔄 正在前往 {slot_id} 号槽位放置...")
            arm.place(slot_id)
            
            print("🔄 动作完成，返回最高观测点...")
            arm.go_observe()
            
            print(f"✅ 【 {slot_id} 号槽位 】 测试完美通过！")
            time.sleep(0.5)

        print("\n🎉 恭喜！所有已标定的槽位全流程测试完毕！")

    except Exception as e:
        print(f"\n❌ 灾难性异常: {e}")
        arm.emergency_stop()

if __name__ == "__main__":
    try:
        run_full_test()
    except KeyboardInterrupt:
        print("\n👋 强制退出测试。")