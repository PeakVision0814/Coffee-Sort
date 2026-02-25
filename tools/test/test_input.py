# -*- coding: utf-8 -*-
# scripts/test_input.py

import sys
import os
import time

# 路径处理，确保能导入 config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymycobot import MyCobot280
from config import settings

def monitor_pin_input():
    # 1. 连接机械臂
    try:
        mc = MyCobot280(settings.PORT, settings.BAUD)
        print(f"✅ 连接成功: {settings.PORT}")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    # 2. 设置要监测的引脚 (G36 是最安全的测试对象，因为它是纯输入)
    # 你也可以改成 2, 5, 26 等
    PIN = 35
    
    print(f"\n--- 开始监测 G{PIN} 引脚电平 ---")
    print("如果不接线，通常为 0 (或浮动)；")
    print("如果接入 3.3V 高电平，应变为 1。")
    print("按 Ctrl+C 停止...\n")

    last_status = -1

    try:
        while True:
            # 获取引脚状态: 0=低电平(无电/接地), 1=高电平(有电/3.3V)
            # 引用:
            current_status = mc.get_basic_input(PIN)
            
            # 只有状态改变时才打印，或者每隔一定时间打印
            if current_status != last_status:
                if current_status == 1:
                    print(f"⚡检测到高电平 (通电/Signal ON) - 值: {current_status}")
                else:
                    print(f"⚪检测到低电平 (断电/Signal OFF) - 值: {current_status}")
                
                last_status = current_status
            
            # 稍作延时，避免刷屏太快
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n监测已停止")

if __name__ == "__main__":
    monitor_pin_input()