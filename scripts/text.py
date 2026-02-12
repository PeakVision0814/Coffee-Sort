# -*- coding: utf-8 -*-
# scripts/send_plc_signal.py

import sys
import os
import time

# 路径处理
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymycobot import MyCobot280
from config import settings

def keep_sending_high_signal():
    # 1. 连接机械臂
    try:
        mc = MyCobot280(settings.PORT, settings.BAUD)
        print(f"✅ 已连接机械臂: {settings.PORT}")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    # 2. 设置输出引脚
    # 必须使用支持输出的引脚：推荐 G2 或 G5
    # 绝对不能用 G35/G36 (它们是纯输入)
    PLC_PIN = 5

    print(f"\n--- 开始向 PLC 发送高电平信号 (引脚: G{PLC_PIN}) ---")
    print("⚡ 状态: HIGH (3.3V)")
    print("⚠️  警告: 请确保已通过继电器/光耦连接到 PLC，不要直连 24V！")
    print("按 Ctrl+C 停止输出...\n")

    try:
        while True:
            # set_basic_output(pin_no, pin_signal)
            # 0 = 低电平, 1 = 高电平
            mc.set_basic_output(PLC_PIN, 1)
            
            # 打印状态让用户知道程序活着
            print(f"\r>>> [正在发送] G{PLC_PIN} -> High Level (1) ...", end="")
            
            # 每隔 1 秒重发一次（虽然引脚状态会保持，但循环发送更稳妥）
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🛑 用户停止")
    finally:
        # 脚本结束时，你可以选择复位成低电平，或者保持高电平
        # 这里为了安全，我们将其复位为 0 (低电平)
        mc.set_basic_output(PLC_PIN, 0)
        print(f"--- 信号已切断 (G{PLC_PIN} -> Low) ---")

if __name__ == "__main__":
    keep_sending_high_signal()