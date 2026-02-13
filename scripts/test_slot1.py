# -*- coding: utf-8 -*-
# scripts/test_slot1.py

import sys
import os
import time

# 路径处理
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.arm_control import ArmController

def test_sequence():
    print("🚀 正在初始化机械臂...")
    arm = ArmController()
    
    if not arm.is_connected:
        print("❌ 连接失败，请检查端口")
        return

    print("\n========== 测试开始 ==========")
    print("⚠️ 请确保机械臂周围没有障碍物！")
    
    # 1. 归位
    input("👉 按回车键：前往 [抓取观测点] ...")
    arm.go_observe()
    
    # 2. 抓取动作测试
    print("\n准备抓取...")
    input("👉 按回车键：执行 [下抓 -> 闭合气爪 -> 抬起] ...")
    arm.pick()
    print("✅ 抓取完成！请检查物品是否抓稳。")
    
    # 3. 放置动作测试
    print("\n准备前往1号位...")
    input("👉 按回车键：执行 [前往1号上方 -> 下放 -> 松开气爪 -> 抬起] ...")
    arm.place(1) # 传入 Slot ID 1
    
    print("\n========== 测试结束 ==========")
    print("✅ 流程跑通！如果动作正常，请继续测量其他槽位。")

if __name__ == "__main__":
    test_sequence()