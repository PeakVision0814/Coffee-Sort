# -*- coding: utf-8 -*-
# tests/test_plc_write.py

import snap7
from snap7.util import set_bool, get_bool
import time
import sys

# 替换为你的 PLC 实际 IP 地址
PLC_IP = '192.168.0.10'
RACK = 0
SLOT = 1  # 大部分 S7-1200/1500 是 0 和 1

# 地址解析: 1.4.4 -> DB1.DBX4.4
DB_NUMBER = 1
BYTE_OFFSET = 4
BIT_OFFSET = 4

def write_plc_bit():
    print("="*50)
    print("🚀 PLC 网络写入测试工具 (Snap7)")
    print(f"📡 目标地址: DB{DB_NUMBER}.DBX{BYTE_OFFSET}.{BIT_OFFSET} (IOTstart)")
    print("="*50)

    plc = snap7.client.Client()
    try:
        print(f"正在连接 PLC ({PLC_IP})...")
        plc.connect(PLC_IP, RACK, SLOT)
        if plc.get_connected():
            print("✅ 连接成功！\n")
        else:
            print("❌ 连接失败！")
            return
    except Exception as e:
        print(f"❌ 连接异常: {e}")
        return

    try:
        while True:
            # 1. 先读取当前这个字节的状态
            data = plc.db_read(DB_NUMBER, BYTE_OFFSET, 1)
            current_status = get_bool(data, 0, BIT_OFFSET)
            
            status_text = "🟢 ON (True)" if current_status else "⚪ OFF (False)"
            print(f"当前 IOTstart 状态: {status_text}")
            
            # 2. 交互式控制
            user_input = input("👉 请输入 1 开启，0 关闭，q 退出: ").strip()
            
            if user_input.lower() == 'q':
                break
            elif user_input == '1':
                target_value = True
            elif user_input == '0':
                target_value = False
            else:
                print("⚠️ 输入无效，请输入 1 或 0。")
                continue

            # 3. 执行“读-改-写”核心动作
            # 重新读取一次确保数据最新
            data = plc.db_read(DB_NUMBER, BYTE_OFFSET, 1)
            # 修改指定的那个位
            set_bool(data, 0, BIT_OFFSET, target_value)
            # 写入整个字节回 PLC
            plc.db_write(DB_NUMBER, BYTE_OFFSET, data)
            
            print(f"⚡ 已发送写入指令 -> {target_value}\n")
            time.sleep(0.1) # 稍微等待让 PLC 反应

    except Exception as e:
        print(f"\n❌ 通信过程中发生异常: {e}")
    finally:
        plc.disconnect()
        print("👋 已断开与 PLC 的连接。")

if __name__ == "__main__":
    write_plc_bit()