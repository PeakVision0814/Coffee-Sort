# -*- coding: utf-8 -*-
# scripts/test_cylinder_g36.py

import sys
import os
import time

# 将项目根目录添加到搜索路径，解决 config 导入问题
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymycobot import MyCobot280
from config import settings

def test_g36_cylinder():
    # 1. 初始化连接
    # 请确保 settings.py 中的 PORT（如 'COM3'）和 BAUD（115200）正确
    mc = MyCobot280(settings.PORT, settings.BAUD)
    time.sleep(1)
    
    # 定义引脚号
    PIN = 2
    
    print(f"--- 开始气爪测试 (引脚: G{PIN}) ---")
    print("注意：请确保未连接 Grove 1 设备，否则 G36 可能失效。")

    try:
        # 进行 3 次开关循环
        for i in range(3):
            print(f"\n[循环 {i+1}]")
            
            # --- 动作：开启 ---
            # 根据官方文档：0 为低电平，通常用于驱动继电器吸合
            print(f">>> 发送信号: 0 (低电平 - 尝试开启气爪)")
            mc.set_basic_output(PIN, 0) 
            time.sleep(2)
            
            # --- 动作：关闭 ---
            # 根据官方文档：1 为高电平，通常用于断开继电器
            print(f">>> 发送信号: 1 (高电平 - 尝试关闭气爪)")
            mc.set_basic_output(PIN, 1) 
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n用户中断测试")
    except Exception as e:
        print(f"运行出错: {e}")
    finally:
        # 测试结束，恢复为高电平停止状态
        mc.set_basic_output(PIN, 1)
        print("--- 测试完成，引脚已复位 ---")

if __name__ == "__main__":
    test_g36_cylinder()