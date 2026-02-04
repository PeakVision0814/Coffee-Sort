import time
import numpy as np
import cv2
from config import settings

class MockMyCobot:
    """
    虚拟机械臂：用于无硬件时的逻辑调试
    """
    def __init__(self, port, baud):
        print(f"\n🚀 [仿真] 虚拟机械臂已启动 (端口: {port})")
        # 初始化为观测点坐标
        self.coords = settings.OBSERVE_COORDS[:] 
        self.gripper_value = 100 # 100=开, 0=闭

    def power_on(self):
        print("⚡ [仿真] 机械臂上电")

    def get_coords(self):
        # 返回当前记录的虚拟坐标
        return self.coords

    def send_coords(self, coords, speed, mode):
        print(f"🦾 [仿真] 移动到: {coords} | 速度: {speed}")
        # 模拟物理运动耗时 (0.5秒)
        time.sleep(0.5)
        # 更新内部坐标，假装已经到了
        self.coords = coords

    def set_gripper_value(self, value, speed):
        self.gripper_value = value
        state = "张开 (Open)" if value > 50 else "闭合 (Close)"
        print(f"🖐️ [仿真] 夹爪动作: {state}")
        time.sleep(0.5)

class MockCamera:
    """
    虚拟摄像头：生成带有噪点和文字的测试画面
    """
    def __init__(self, index=0, backend=None):
        print(f"📷 [仿真] 虚拟摄像头已启动")
        self.frame_count = 0

    def set(self, prop, val):
        pass # 假装设置成功

    def read(self):
        # 1. 创建一个黑底图片 (480x640)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # 2. 模拟动态噪点 (证明画面在刷新)
        noise = np.random.randint(0, 30, (480, 640, 3), dtype=np.uint8)
        frame = cv2.add(frame, noise)

        # 3. 绘制提示文字
        self.frame_count += 1
        cv2.putText(frame, f"SIMULATION MODE {self.frame_count}", (180, 240), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        
        # 4. 绘制参考线 (模拟视觉区域)
        cv2.rectangle(frame, (200, 150), (440, 330), (0, 255, 0), 2)
        cv2.putText(frame, "Target Area", (210, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # 控制帧率，防止CPU跑满
        time.sleep(0.03) 
        return True, frame

    def release(self):
        print("📷 [仿真] 摄像头释放")