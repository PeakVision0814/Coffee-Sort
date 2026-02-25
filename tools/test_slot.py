# -*- coding: utf-8 -*-
# tests/test_slot.py
import sys
import os
import time

# 将项目根目录加入环境变量
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from modules.arm_control import ArmController
from config import settings

# 根据系统环境引入按键监听模块
try:
    import msvcrt
    def wait_for_space():
        """Windows 下等待空格键按下 (不需要按回车)"""
        print("👉 请按【空格键】执行下一步 (按 Q 提前终止测试)...")
        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key == b' ':
                    print("▶️ 执行中...")
                    return True
                elif key.lower() == b'q':
                    print("\n⏹️ 终止当前槽位测试。")
                    return False
            time.sleep(0.05)
except ImportError:
    def wait_for_space():
        """Mac/Linux 下的降级方案"""
        res = input("👉 请按【回车键】执行下一步 (输入 q 退出): ")
        return res.lower() != 'q'

def test_single_slot_stepper(slot_id):
    print(f"\n" + "="*50)
    print(f"🚀 开始步进测试: [抓取区] 搬运至 [槽位 {slot_id}]")
    print("="*50)
    
    arm = ArmController()
    if not arm.is_connected:
        print("❌ 机械臂连接失败，请检查连线或端口配置！")
        return

    # 提取坐标配置
    p = settings.PICK_POSES
    r = settings.STORAGE_RACKS.get(slot_id)
    if not r:
        print(f"❌ 找不到槽位 {slot_id} 的坐标配置！")
        return

    # 将完整动作解构成 16 个独立的步骤
    steps = [
        ("动作初始化", "张开气爪", lambda: arm.gripper_open()),
        ("前往抓取区", "最高观测点 (Observe)", lambda: arm.move_to_angles(p["observe"], arm.fly_speed, 0)),
        ("准备抓取",   "下降至中间过渡点 (Mid)", lambda: arm.move_to_angles(p["mid"], arm.fly_speed, 0)),
        ("精确定位",   "下探至最低抓取点 (Grab)", lambda: arm.move_to_angles(p["grab"], arm.speed, 0)),
        ("执行抓取",   "闭合气爪", lambda: arm.gripper_close()),
        ("稳定等待",   "等待 1 秒让气爪夹紧", lambda: time.sleep(1)),
        ("拔起物体",   "原路拔起至中间点 (Mid)", lambda: arm.move_to_angles(p["mid"], arm.fly_speed, 0)),
        ("撤离抓取区", "退回最高观测点 (Observe)", lambda: arm.move_to_angles(p["observe"], arm.fly_speed, 0)),
        
        (f"飞往槽位 {slot_id}", "前往最高安全跨越点 (High)", lambda: arm.move_to_angles(r["high"], arm.fly_speed, 0)),
        (f"准备放置",   "下降至中间过渡点 (Mid)", lambda: arm.move_to_angles(r["mid"], arm.fly_speed, 0)),
        (f"精确定位",   "下探至最低放置点 (Low)", lambda: arm.move_to_angles(r["low"], arm.speed, 0)),
        ("执行放置",   "张开气爪释放物品", lambda: arm.gripper_open()),
        ("稳定等待",   "等待 1 秒让物品落稳", lambda: time.sleep(1)),
        ("拔起撤离",   "原路拔起至中间点 (Mid)", lambda: arm.move_to_angles(r["mid"], arm.fly_speed, 0)),
        ("彻底撤离",   "退回最高安全跨越点 (High)", lambda: arm.move_to_angles(r["high"], arm.fly_speed, 0)),
        ("测试结束",   "返回抓取最高观测点 (Observe)", lambda: arm.move_to_angles(p["observe"], arm.fly_speed, 0))
    ]

    try:
        for i, (stage, desc, action) in enumerate(steps):
            print(f"\n[{i+1}/{len(steps)}] 阶段: {stage}")
            print(f"   目标: {desc}")
            
            # 等待用户按空格
            if not wait_for_space():
                break
                
            # 执行底层指令
            action()
            
            # 给予电机一点缓冲时间启动，避免立刻刷出下一条提示
            time.sleep(0.5) 
            
        print(f"\n✅ 槽位 {slot_id} 步进测试结束！")

    except Exception as e:
        print(f"\n❌ 测试过程中发生异常: {e}")
        arm.emergency_stop()

if __name__ == "__main__":
    print("\n" + "★"*50)
    print("🤖 智能分拣系统 - 步进式(Step-by-Step)排错工具")
    print("★"*50)
    
    while True:
        try:
            user_input = input("\n⌨️ 请输入要测试的槽位编号 (1-6)，输入 q 退出: ").strip()
            
            if user_input.lower() == 'q':
                print("👋 退出测试工具。")
                break
                
            slot_id = int(user_input)
            
            if 1 <= slot_id <= 6:
                rack_data = settings.STORAGE_RACKS.get(slot_id)
                if rack_data and sum(rack_data["low"]) != 0: 
                    test_single_slot_stepper(slot_id)
                else:
                    print(f"⚠️ 警告：检测到 config/settings.py 中槽位 {slot_id} 的坐标似乎未配置！")
            else:
                print("⚠️ 槽位编号必须在 1 到 6 之间！")
                
        except ValueError:
            print("⚠️ 请输入有效的数字！")
        except KeyboardInterrupt:
            print("\n👋 强制退出测试。")
            break