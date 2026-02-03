import time
import sys
import os

# 路径处理
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
            self.mc.power_on()
            time.sleep(1)
            
            if not self.mc.is_power_on():
                print("⚠️ 机械臂未上电，尝试强制上电...")
                self.mc.power_on()
            
            # 1=线性运动(Coord), 0=非线性(Angle)
            self.move_mode = 1 
            self.speed = 50
            
        except Exception as e:
            print(f"❌ 机械臂初始化失败: {e}")
            self.mc = None

    def go_home(self):
        """回到安全原点"""
        print("🤖 动作: 回原点")
        if self.mc:
            self.mc.send_angles(settings.HOME_POSE, self.speed)
            time.sleep(3)

    def go_observe(self):
        """去观测点"""
        print("🤖 动作: 去观测姿态")
        if self.mc:
            self.mc.send_angles(settings.OBSERVE_POSE, self.speed)
            time.sleep(3)

    def gripper_open(self):
        """张开夹爪"""
        print("   -> 夹爪张开")
        if self.mc:
            self.mc.set_gripper_value(100, 70)
            time.sleep(1.5)

    def gripper_close(self):
        """闭合夹爪"""
        print("   -> 夹爪闭合")
        if self.mc:
            self.mc.set_gripper_value(10, 70)
            time.sleep(1.5)

    def pick(self, target_x, target_y):
        """抓取动作"""
        if not self.mc: return

        print(f"🤖 动作: 执行抓取 -> ({target_x:.1f}, {target_y:.1f})")
        
        # 保持垂直向下姿态
        current_head = [-180, 0, 0]

        # 1. 移动到上方 (Safe Z)
        print(f"   1. 移动到上方 (Z={settings.SAFE_Z})")
        self.mc.send_coords([target_x, target_y, settings.SAFE_Z] + current_head, self.speed, self.move_mode)
        time.sleep(3)

        # 2. 张开
        self.gripper_open()

        # 3. 下降 (Pick Z)
        print(f"   2. 下降抓取 (Z={settings.PICK_Z})")
        self.mc.send_coords([target_x, target_y, settings.PICK_Z] + current_head, self.speed, self.move_mode)
        time.sleep(2.5)

        # 4. 闭合
        self.gripper_close()

        # 5. 抬起 (Safe Z)
        print(f"   3. 抬起 (Z={settings.SAFE_Z})")
        self.mc.send_coords([target_x, target_y, settings.SAFE_Z] + current_head, self.speed, self.move_mode)
        time.sleep(2)
        
        print("✅ 抓取完成")

    # --- 之前可能缺失或缩进错误的 Place 函数 ---
    def place(self, bin_type="A"):
        """放置动作"""
        if not self.mc: return
        
        print(f"🤖 动作: 放置到 {bin_type} 仓")
        
        target_coords = settings.BIN_A_COORDS if bin_type == "A" else settings.BIN_B_COORDS
        
        # 准备高空点
        safe_target = target_coords.copy()
        safe_target[2] = settings.SAFE_Z 
        
        # 1. 平移到上方
        print(f"   1. 移动到仓库上方")
        self.mc.send_coords(safe_target, self.speed, self.move_mode)
        time.sleep(3)
        
        # 2. 下降放置 (使用真实的仓库高度)
        print(f"   2. 下降放置 (Z={target_coords[2]})")
        self.mc.send_coords(target_coords, self.speed, self.move_mode)
        time.sleep(2.5)
        
        # 3. 松开
        self.gripper_open()
        
        # 4. 抬起
        print(f"   3. 抬起撤离")
        self.mc.send_coords(safe_target, self.speed, self.move_mode)
        time.sleep(2)
        
        # 5. 回观测点
        self.go_observe()
        print("✅ 放置完成")