# -*- coding: utf-8 -*-
# tests/test_gpio.py
import sys
import os
import time
from datetime import datetime

# 将项目根目录加入环境变量
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from config import settings

try:
    from pymycobot import MyCobot280
except ImportError:
    from pymycobot import MyCobot as MyCobot280

def test_gpio():
    print("="*50)
    print("🛠️ 机械臂底座 GPIO 物理引脚诊断工具")
    print("="*50)
    
    print(f"🔌 正在连接机械臂 (端口: {settings.PORT}, 波特率: {settings.BAUD})...")
    try:
        mc = MyCobot280(settings.PORT, settings.BAUD)
        time.sleep(1)
        if not mc.is_power_on():
            mc.power_on()
        print("✅ 连接成功！开始实时监控引脚电平...\n")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    print("👉 请观察以下输出。按 Ctrl+C 退出。")
    print("   提示: 如果数字在 0 和 1 之间疯狂跳动，说明引脚悬空(Floating)或未共地！")
    print("-" * 50)

    try:
        while True:
            # 读取 G35 和 G36
            val_35 = mc.get_basic_input(35)
            val_36 = mc.get_basic_input(36)

            # 过滤掉偶尔的串口通信丢失 (None)
            if val_35 is not None and val_36 is not None:
                
                # 终端动态刷新显示
                now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                
                # 用不同的颜色/符号直观显示高低电平
                status_35 = "🔴 高电平 (1)" if val_35 == 1 else "⚪ 低电平 (0)"
                status_36 = "🔴 高电平 (1)" if val_36 == 1 else "⚪ 低电平 (0)"

                # \r 让输出保持在同一行刷新，不会疯狂刷屏
                sys.stdout.write(f"\r[{now}]  G35: {status_35}   |   G36: {status_36}        ")
                sys.stdout.flush()
                
            time.sleep(0.05) # 50毫秒刷新一次，捕捉抖动绰绰有余

    except KeyboardInterrupt:
        print("\n\n⏹️ 测试已终止。")
    finally:
        mc.power_off()

if __name__ == "__main__":
    test_gpio()