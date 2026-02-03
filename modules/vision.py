import cv2
import numpy as np
import json
import os
import sys

# 尝试导入 Aruco 库，如果报错则提示安装
try:
    from cv2 import aruco
except ImportError:
    print("⚠️ 警告: 未找到 cv2.aruco 模块，请运行 'pip install opencv-contrib-python' 安装")
    aruco = None

class VisionSystem:
    def __init__(self, config_dir="config"):
        # 1. 路径处理
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.config_dir = os.path.join(self.base_dir, config_dir)
        
        # 2. 加载相机内参
        matrix_path = os.path.join(self.config_dir, "camera_matrix.npz")
        if os.path.exists(matrix_path):
            data = np.load(matrix_path)
            self.mtx = data['mtx']
            self.dist = data['dist']
            print("✅ [Vision] 相机内参已加载")
        else:
            print("⚠️ [Vision] 未找到相机内参，将跳过畸变矫正")
            self.mtx = None
            self.dist = None

        # 3. 加载手眼标定参数
        hand_eye_path = os.path.join(self.config_dir, "calibration.json")
        if os.path.exists(hand_eye_path):
            with open(hand_eye_path, 'r') as f:
                self.calib_data = json.load(f)
            self.scale = self.calib_data.get("scale_mm_per_pixel", 0)
            self.offset = self.calib_data.get("camera_gripper_offset", [0, 0])
            print(f"✅ [Vision] 手眼标定参数已加载: 1px={self.scale:.4f}mm")
        else:
            print("⚠️ [Vision] 未找到手眼标定文件")
            self.scale = 0
            self.offset = [0, 0]

    def process_frame(self, frame):
        """
        主处理流程：去畸变 -> 找最近物体 -> 返回坐标
        """
        # 1. 去畸变
        if self.mtx is not None:
            h, w = frame.shape[:2]
            newcameramtx, roi = cv2.getOptimalNewCameraMatrix(self.mtx, self.dist, (w,h), 1, (w,h))
            dst = cv2.undistort(frame, self.mtx, self.dist, None, newcameramtx)
            frame = dst

        # 2. 寻找最靠前的物体 (The Nearest Object)
        target_center = self.find_nearest_object(frame)
        
        real_world_offset = None
        if target_center:
            # 画出红点
            cv2.circle(frame, target_center, 8, (0, 0, 255), -1)
            cv2.putText(frame, "TARGET", (target_center[0]+10, target_center[1]), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            
            # 3. 计算物理偏差
            h, w = frame.shape[:2]
            center_x, center_y = w // 2, h // 2
            
            dx_pixel = target_center[0] - center_x
            dy_pixel = target_center[1] - center_y
            
            # 转换为毫米 (注意：正负号根据之前的 test_moves.py 测试结果调整)
            # 假设之前测试是 X反向, Y反向 (示例)
            dx_mm = -dx_pixel * self.scale
            dy_mm = -dy_pixel * self.scale
            
            real_world_offset = (dx_mm, dy_mm)
            
            # 显示信息
            text = f"Offset: X={dx_mm:.1f}, Y={dy_mm:.1f}"
            cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        return frame, real_world_offset

    def find_nearest_object(self, img):
        """
        寻找画面中 Y 坐标最大 (最靠下/最靠前) 的物体
        """
        # 转灰度
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 预处理：模糊 + 阈值 (识别深色物体)
        # 如果咖啡盒是深色的，用 THRESH_BINARY_INV
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 80, 255, cv2.THRESH_BINARY_INV)
        
        # 找轮廓
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        valid_objects = []
        
        for c in contours:
            area = cv2.contourArea(c)
            # 过滤太小的噪点 (比如面积 < 1000)
            if area > 1000:
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    
                    # 记录 (cY, cX, center_tuple)
                    # 我们用 cY 作为排序依据
                    valid_objects.append((cY, (cX, cY)))
        
        if valid_objects:
            # 排序：找 Y 最大的 (假设传送带从上往下走，最下面的就是最先到的)
            # 如果你的传送带方向相反，就把 reverse=True 改为 False
            valid_objects.sort(key=lambda x: x[0], reverse=True)
            
            # 返回最靠前的物体的中心点
            return valid_objects[0][1]
            
        return None

    def detect_aruco_marker(self, frame):
        """
        检测画面中是否存在 Aruco 二维码
        返回: 识别到的 ID 列表 (例如 [1, 2])，如果没有则返回 []
        """
        if aruco is None:
            return []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 使用标准的 4x4 字典 (常用)
        aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
        parameters = aruco.DetectorParameters()
        
        # 检测
        corners, ids, rejectedImgPoints = aruco.detectMarkers(gray, aruco_dict, parameters=parameters)
        
        detected_ids = []
        if ids is not None:
            # ids 是一个 numpy 数组，展平为列表
            detected_ids = ids.flatten().tolist()
            
            # 画出来看看 (可选)
            aruco.drawDetectedMarkers(frame, corners, ids)
            
        return detected_ids

# --- 单元测试 ---
if __name__ == "__main__":
    cap = cv2.VideoCapture(0)
    vision = VisionSystem()
    print(">>> 视觉测试启动 (寻找最靠下的物体)...")
    
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        # 测试 Aruco
        ids = vision.detect_aruco_marker(frame)
        if ids:
            cv2.putText(frame, f"Aruco IDs: {ids}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
            
        # 测试物体识别
        processed_frame, offset = vision.process_frame(frame)
        
        cv2.imshow("New Vision Test", processed_frame)
        if cv2.waitKey(1) == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()