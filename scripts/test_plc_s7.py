import snap7
from snap7.util import get_bool

def test_plc_communication():
    # 1. 初始化客户端
    client = snap7.client.Client()
    
    # PLC 参数
    ip = '192.168.0.10'
    rack = 0  # 物理机架号，通常为 0
    slot = 1  # CPU 槽位，S7-1200/1500 通常为 1，S7-300 通常为 2
    db_number = 1  # 对应你地址中的 DB1
    
    try:
        # 2. 建立连接
        client.connect(ip, rack, slot)
        
        if client.get_connected():
            print(f"成功连接至 PLC: {ip}")
            
            # 3. 读取 DB 块数据
            # read_area(区类型, DB号, 起始地址, 读取长度)
            # S7AreaDB = 0x84
            # 我们从 0 开始读 2 个字节，覆盖了 0.x 和 1.x
            data = client.db_read(db_number, 0, 2)
            
            print("--- 槽位状态读取结果 ---")
            
            # 4. 解析位状态 (1.0.4 到 1.1.1)
            # 格式：get_bool(数据块, 字节索引, 位索引)
            
            # 读取 Byte 0 的位
            for bit in range(4, 8):
                status = get_bool(data, 0, bit)
                print(f"地址 DB{db_number}.DBX0.{bit}: {'ON' if status else 'OFF'}")
                
            # 读取 Byte 1 的位
            for bit in range(0, 2):
                status = get_bool(data, 1, bit)
                print(f"地址 DB{db_number}.DBX1.{bit}: {'ON' if status else 'OFF'}")
                
        else:
            print("连接失败，请检查 IP 或网络设置。")

    except Exception as e:
        print(f"发生错误: {e}")
        
    finally:
        # 5. 断开连接
        client.disconnect()
        print("通信已关闭。")

if __name__ == "__main__":
    test_plc_communication()