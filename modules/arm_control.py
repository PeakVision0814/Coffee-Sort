import time
import sys
import os
from config import settings

# 导入驱动
try:
    from pymycobot import MyCobot280
except ImportError:
    from pymycobot import MyCobot as MyCobot280

class ArmController:
    def __init__(self):
        print(f">>> [Arm] 初始化驱动 (端口: {settings.PORT})...")
        self.mc = None
        self.is_connected = False

        if settings.SIMULATION_MODE:
            print("⚠️ 仿真模式")
            return

        try:
            # 1. 连接
            self.mc = MyCobot280(settings.PORT, settings.BAUD)
            time.sleep(0.5)
            
            # 2. 上电
            if not self.mc.is_power_on():
                self.mc.power_on()
                time.sleep(0.5)
            
            # 3. 初始状态
            self.mc.set_gripper_value(100, 70) # 张开
            
            # 速度设置
            self.speed = 80
            
            # 4. 测试通讯
            angles = self.mc.get_angles()
            if angles:
                print(f"✅ [Arm] 连接成功，当前角度: {angles}")
                self.is_connected = True
                self.mc.set_color(0, 255, 0)
            else:
                print("❌ [Arm] 串口打开但读取失败")
                
        except Exception as e:
            print(f"❌ [Arm] 连接异常: {e}")

    # --- 核心工具 ---
    def move_to_angles(self, angles, speed, delay_time):
        """最稳健的移动方式：发送角度 -> 等待"""
        if not self.is_connected: return
        try:
            self.mc.send_angles(angles, speed)
            time.sleep(delay_time)
        except Exception as e:
            print(f"⚠️ 移动指令发送失败: {e}")

    # --- 业务动作 ---

    def go_observe(self):
        """
        前往抓取观测点 (安全复位)
        🔥 修复：增加强制上电逻辑，解决待机垂落后无法复位的问题
        """
        if not self.is_connected: return
        
        print(">>> [Arm] 🔄 正在唤醒并归位...")
        try:
            # 1. 强制上电 (Torque On)
            # 防止机械臂因长时间待机掉电，或者此时正处于下垂状态
            self.mc.power_on()
            time.sleep(0.5) # 给一点时间充能锁死舵机
            
            # 2. 发送归位指令
            target = settings.PICK_POSES["observe"]
            # 稍微给多一点时间(2.0s)，因为如果从趴着的状态起来，路程较长
            self.move_to_angles(target, self.speed, 2.0) 
            
            print(">>> [Arm] ✅ 已安全归位")
        except Exception as e:
            print(f"❌ 归位失败: {e}")

    def pick(self):
        """执行抓取流程"""
        if not self.is_connected: return
        print(f"🤖 [Arm] 执行抓取")

        # 为了安全，抓取前其实也可以再次确保上电，但 go_observe 已经做了
        # 这里保持高效，不再重复 power_on，除非发现经常抓取失败

        pose_high = settings.PICK_POSES["observe"] # 高位
        pose_low  = settings.PICK_POSES["grab"]    # 低位
        
        # 1. 下抓
        print("   1️⃣ 下探抓取")
        self.mc.set_gripper_value(100, 70) 
        self.move_to_angles(pose_low, self.speed, 1.2)
        
        # 2. 闭合
        print("   2️⃣ 闭合夹爪")
        self.mc.set_gripper_value(10, 70)
        time.sleep(0.8)

        # 3. 抬起
        print("   3️⃣ 抬起")
        self.move_to_angles(pose_high, self.speed, 1.0)

    def place(self, slot_id):
        """放置到槽位"""
        if not self.is_connected: return
        
        rack_data = settings.STORAGE_RACKS.get(slot_id)
        if not rack_data:
            print(f"❌ 无效槽位: {slot_id}")
            return

        print(f"🤖 [Arm] 执行放置 -> {slot_id}号位")
        
        pose_high = rack_data["high"]
        pose_low  = rack_data["low"]

        # 1. 移动到槽位上方 (High)
        print("   4️⃣ 移动到槽位上方")
        self.move_to_angles(pose_high, self.speed, 2.0) 

        # 2. 下放 (Low)
        print("   5️⃣ 下放")
        self.move_to_angles(pose_low, self.speed, 1.2)

        # 3. 松开
        print("   6️⃣ 松开")
        self.mc.set_gripper_value(100, 70)
        time.sleep(0.5) 

        # 4. 抬起 (High)
        print("   7️⃣ 抬起离开")
        self.move_to_angles(pose_high, self.speed, 1.0)

        # 5. 归位
        self.go_observe()