import sys
import time
import os

# 将项目根目录加入路径，以便后续能导入 config 模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from pymycobot import MyCobot280
except ImportError:
    print("错误: 未安装 pymycobot 库。请运行 pip install pymycobot")
    sys.exit(1)

# --- 配置区域 ---
# 在 Windows 上通常是 COM3, COM4 等。请在设备管理器中确认 CP210x 的端口
PORT = "COM3"  
BAUD = 115200  # M5 版本固定波特率

def test_arm():
    print(f"正在尝试连接机械臂 ({PORT})...")
    try:
        # 1. 初始化连接
        mc = MyCobot280(PORT, BAUD)
        time.sleep(0.5)
        print("✅ 串口连接成功！")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print("请检查：1. USB线是否插好 2. 端口号是否正确 3. 驱动是否安装")
        return

    # 2. 基础检查
    # 检查是否上电
    if not mc.is_power_on():
        print("检测到机械臂未上电，正在尝试上电...")
        mc.power_on()
        time.sleep(1)
    
    # 读取版本和角度
    version = mc.get_system_version()
    angles = mc.get_angles()
    coords = mc.get_coords()
    
    print(f"\n--- 状态信息 ---")
    print(f"固件版本: {version}")
    print(f"当前角度: {angles}")
    print(f"当前坐标: {coords}")
    print("----------------\n")

    # 3. 动作测试 (安全起见，动作幅度很小)
    print(">>> 开始动作测试：回零位 (Home)")
    mc.send_angles([0, 0, 0, 0, 0, 0], 50)
    time.sleep(3) # 等待动作完成

    print(">>> 动作测试：点头 (Joint 4)")
    mc.send_angle(4, 20, 50)
    time.sleep(1)
    mc.send_angle(4, 0, 50)
    time.sleep(1)

    # 4. 夹爪测试
    # 注意：确保夹爪已连接到 Atom 顶端接口
    print(">>> 夹爪测试：尝试开合")
    # 先张开 (100)
    print("   Open...")
    mc.set_gripper_value(100, 70) 
    time.sleep(2)
    # 后闭合 (0)
    print("   Close...")
    mc.set_gripper_value(0, 70)
    time.sleep(2)
    
    # 5. 放松舵机
    print("\n✅ 测试完成。放松机械臂，你可以手动移动它了。")
    mc.release_all_servos()

if __name__ == "__main__":
    test_arm()