import time
import sys
import os

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
            self.move_mode = 1 
            self.speed = 80 # 稍微提速一点
            
        except Exception as e:
            print(f"❌ 机械臂初始化失败: {e}")
            self.mc = None

    # --- 基础动作 ---
    def go_home(self):
        if self.mc:
            self.mc.send_angles(settings.HOME_POSE, self.speed)
            time.sleep(3)

    def go_observe(self):
        if self.mc:
            self.mc.send_angles(settings.OBSERVE_POSE, self.speed)
            time.sleep(3)

    def gripper_open(self):
        if self.mc:
            self.mc.set_gripper_value(100, 70)
            time.sleep(1.0)

    def gripper_close(self):
        if self.mc:
            self.mc.set_gripper_value(10, 70)
            time.sleep(1.0)

    # --- 核心业务动作 ---
    
    def pick(self, target_x, target_y):
        """抓取逻辑 (不变)"""
        if not self.mc: return
        print(f"🤖 [动作] 抓取 -> ({target_x:.1f}, {target_y:.1f})")
        
        current_head = [-180, 0, 0]
        
        # 1. 移动到上方
        self.mc.send_coords([target_x, target_y, settings.SAFE_Z] + current_head, self.speed, self.move_mode)
        time.sleep(2.5)
        self.gripper_open()

        # 2. 下降
        self.mc.send_coords([target_x, target_y, settings.PICK_Z] + current_head, self.speed, self.move_mode)
        time.sleep(2)
        self.gripper_close()

        # 3. 抬起
        self.mc.send_coords([target_x, target_y, settings.SAFE_Z] + current_head, self.speed, self.move_mode)
        time.sleep(2)

    def place(self, slot_id=1):
        """
        🔥 升级版放置逻辑：支持指定槽位 ID
        :param slot_id: 1~6 的整数
        """
        if not self.mc: return
        
        # 1. 查表获取坐标
        # 如果 ID 不在表里（比如 7），默认去 1 号，防止报错
        target_coords = settings.STORAGE_RACKS.get(slot_id, settings.STORAGE_RACKS[1])
        
        print(f"🤖 [动作] 放置 -> {slot_id}号位 {target_coords[:3]}")
        
        # 2. 准备高空点 (使用配置里的 SAFE_Z)
        safe_target = list(target_coords).copy() # 复制一份，防止修改原配置
        safe_target[2] = settings.SAFE_Z 
        
        # 3. 移动到槽位上方
        self.mc.send_coords(safe_target, self.speed, self.move_mode)
        time.sleep(3)
        
        # 4. 下降放置 (使用 target_coords 里的真实高度)
        self.mc.send_coords(target_coords, self.speed, self.move_mode)
        time.sleep(2)
        
        # 5. 松开
        self.gripper_open()
        
        # 6. 抬起
        self.mc.send_coords(safe_target, self.speed, self.move_mode)
        time.sleep(2)
        
        # 7. 回观测点 (准备下一轮)
        self.go_observe()

    def scan_slots(self, vision_system_instance):
        """
        📡 开机巡检逻辑：走遍 6 个槽，看有没有东西
        :param vision_system_instance: 传入 vision 对象，用于识别
        :return: 库存状态字典 {1:0, 2:1, ...}
        """
        if not self.mc: return {}
        
        print("\n🛰️ [系统] 开始全场库存扫描...")
        slot_status = {}
        
        # 遍历 1 到 6 号槽
        for i in range(1, 7):
            coords = settings.STORAGE_RACKS.get(i)
            if not coords: continue
            
            print(f"   -> 正在检查 {i} 号位...")
            
            # 1. 移动到槽位正上方 (Safe Z)
            check_pos = list(coords).copy()
            check_pos[2] = settings.SAFE_Z # 必须在高处看，不然撞了
            self.mc.send_coords(check_pos, self.speed, self.move_mode)
            time.sleep(2.5) # 等稳住
            
            # 2. 获取一次画面 (这里需要 main.py 配合传入摄像头画面，或者在这里临时读)
            # 为了简单，我们假设 vision_system_instance 有个方法可以直接读摄像头
            # 但通常 arm 不应该直接操作摄像头。
            # 这里我们只负责"走到位置"，视觉检测在外部做更合适。
            # --- 修正逻辑 ---
            # 我们让 arm 提供一个 generator (生成器)，主程序里每一步都调一下视觉
            pass 
        
        # 为了架构解耦，这个 scan_slots 最好只负责“动作序列”
        # 真正核心的“边走边看”逻辑，我们写在 main.py 里会更灵活
        print("✅ 扫描动作完成")
        return slot_status

    def get_slot_coords(self, slot_id):
        """辅助函数：给外部查坐标用"""
        return settings.STORAGE_RACKS.get(slot_id)