import time
import sys
import os

# 路径处理，确保能导入 config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from pymycobot import MyCobot280
    from config import settings
except ImportError:
    print("❌ 导入失败，请检查 pymycobot 或 config 文件")

class ArmController:
    def __init__(self):
        print(">>> 初始化机械臂控制模块...")
        try:
            self.mc = MyCobot280(settings.PORT, settings.BAUD)
            time.sleep(0.5)
            # 1. 上电
            self.mc.power_on()
            # 2. 稍微等一下
            time.sleep(1)
            # 3. 检查状态
            if not self.mc.is_power_on():
                print("⚠️ 机械臂未上电，尝试强制上电...")
                self.mc.power_on()
            print("✅ 机械臂连接成功")
            
            # 4. 设置运动模式 (1=线性, 0=非线性) -> 抓取建议用线性(1)
            self.move_mode = 1 
            self.speed = 50  # 默认速度
            
        except Exception as e:
            print(f"❌ 机械臂初始化失败: {e}")
            self.mc = None

    def go_home(self):
        """回到安全原点"""
        print("🤖 动作: 回原点")
        self.mc.send_angles(settings.HOME_POSE, self.speed)
        time.sleep(3)

    def go_observe(self):
        """去观测点 (准备拍照)"""
        print("🤖 动作: 去观测姿态")
        self.mc.send_angles(settings.OBSERVE_POSE, self.speed)
        time.sleep(3)

    def gripper_open(self):
        """张开夹爪"""
        print("   -> 夹爪张开")
        self.mc.set_gripper_value(100, 70)
        time.sleep(1.5)

    def gripper_close(self):
        """闭合夹爪"""
        print("   -> 夹爪闭合")
        self.mc.set_gripper_value(10, 70) # 10 表示夹紧，0 可能会死锁，视情况调整
        time.sleep(1.5)

    def pick(self, target_x, target_y):
        """
        核心动作：定点抓取 (门字型轨迹)
        :param target_x: 目标的绝对坐标 X
        :param target_y: 目标的绝对坐标 Y
        """
        if not self.mc: return

        print(f"🤖 动作: 执行抓取 -> ({target_x:.1f}, {target_y:.1f})")
        
        # 0. 确保姿态垂直向下
        current_head = [-180, 0, 0] # rx, ry, rz

        # 1. 移动到目标正上方 (安全高度)
        # 注意：这里 Z 用的是 OBSERV_Z 或者 SAFE_Z
        print(f"   1. 移动到上方 (Z={settings.SAFE_Z})")
        self.mc.send_coords([target_x, target_y, settings.SAFE_Z] + current_head, self.speed, self.move_mode)
        time.sleep(3) # 等待到位

        # 2. 张开夹爪
        self.gripper_open()

        # 3. 垂直下降 (抓取高度)
        print(f"   2. 下降抓取 (Z={settings.PICK_Z})")
        self.mc.send_coords([target_x, target_y, settings.PICK_Z] + current_head, self.speed, self.move_mode)
        time.sleep(2.5)

        # 4. 闭合夹爪
        self.gripper_close()

        # 5. 垂直抬起 (回到安全高度)
        print(f"   3. 抬起 (Z={settings.SAFE_Z})")
        self.mc.send_coords([target_x, target_y, settings.SAFE_Z] + current_head, self.speed, self.move_mode)
        time.sleep(2)
        
        print("✅ 抓取完成")

    def place(self, bin_type="A"):
        """
        放置动作
        :param bin_type: "A" 或 "B"
        """
        print(f"🤖 动作: 放置到 {bin_type} 仓")
        
        # 获取目标仓库坐标
        target_coords = settings.BIN_A_COORDS if bin_type == "A" else settings.BIN_B_COORDS
        
        # 1. 移动到仓库上方 (保持 Z 高度，防止撞墙)
        # 我们先取仓库的 x,y，但高度强制用 SAFE_Z
        safe_target = target_coords.copy()
        safe_target[2] = settings.SAFE_Z 
        
        self.mc.send_coords(safe_target, self.speed, self.move_mode)
        time.sleep(3)
        
        # 2. (可选) 下降一点点放，防止摔坏咖啡
        # self.mc.send_coords(target_coords, self.speed, self.move_mode)
        # time.sleep(2)
        
        # 3. 张开夹爪
        self.gripper_open()
        
        # 4. 回到观测点或原点，准备下一轮
        self.go_observe()
        print("✅ 放置完成，准备就绪")

# --- 单元测试 (模拟模式) ---
if __name__ == "__main__":
    # 如果在家没有机器，这个 main 函数跑不起来
    # 但你可以检查语法有没有错
    print(">>> 正在检查 ArmController 语法...")
    try:
        # 这里尝试实例化，如果没有连接机器会报错并捕获
        arm = ArmController()
        if arm.mc:
            # 如果真的连上了机器 (比如明天)，会跑这个 demo
            arm.go_home()
            arm.go_observe()
            # 假装在 (150, 0) 抓个东西
            arm.pick(150, 0)
            arm.place("A")
    except Exception as e:
        print(f"测试中断 (正常现象，因为没连机器): {e}")
    print(">>> 语法检查通过！")