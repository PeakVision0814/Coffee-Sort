import cv2
import numpy as np
import json
import os
import sys

class VisionSystem:
    def __init__(self, config_dir="config"):
        # 1. 路径处理
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.config_dir = os.path.join(self.base_dir, config_dir)
        
        # 2. 加载相机内参 (用于去畸变)
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

        # 3. 加载手眼标定参数 (用于算坐标)
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
        核心处理函数：去畸变 -> 识别 -> 返回坐标
        """
        # 1. 去畸变 (Undistort)
        if self.mtx is not None:
            h, w = frame.shape[:2]
            newcameramtx, roi = cv2.getOptimalNewCameraMatrix(self.mtx, self.dist, (w,h), 1, (w,h))
            dst = cv2.undistort(frame, self.mtx, self.dist, None, newcameramtx)
            # 裁剪黑边 (可选)
            # x, y, w, h = roi
            # dst = dst[y:y+h, x:x+w]
            frame = dst

        # 2. 图像识别逻辑 (这里演示识别红色物体/色块)
        # 将来这里可以替换为二维码识别或 STag
        target_center = self.detect_color_blob(frame)
        
        real_world_offset = None
        if target_center:
            # 画出中心点
            cv2.circle(frame, target_center, 5, (0, 0, 255), -1)
            
            # 3. 计算物理偏差 (核心数学逻辑)
            # 图像中心坐标
            h, w = frame.shape[:2]
            center_x, center_y = w // 2, h // 2
            
            # 目标相对于画面中心的像素距离
            # 注意：图像坐标系 y 是向下的，x 是向右的
            # 机械臂坐标系取决于安装方向，通常相机 x 对应机械臂 y，需要明天现场确认
            # 这里先假设：图像右(u+) -> 机械臂前(x+), 图像下(v+) -> 机械臂右(y-)
            # *这行代码明天需要现场调试方向*
            dx_pixel = target_center[0] - center_x
            dy_pixel = target_center[1] - center_y
            
            # 转换为毫米
            dx_mm = dx_pixel * self.scale
            dy_mm = dy_pixel * self.scale
            
            # 返回相对于【当前相机中心】的物理偏移量 (x, y)
            # 格式：[x方向偏移, y方向偏移]
            real_world_offset = (dx_mm, dy_mm)
            
            # 在画面上显示信息
            text = f"Offset: X={dx_mm:.1f}mm, Y={dy_mm:.1f}mm"
            cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        return frame, real_world_offset

    def detect_color_blob(self, img):
        """
        简单的颜色识别测试 (识别画面中最显著的深色/黑色物体，模拟识别咖啡盒)
        """
        # 转为灰度
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # 阈值处理 (假设物体是黑色的，背景是亮的)
        # 实际项目中建议用 HSV
        _, thresh = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
        
        # 找轮廓
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # 找最大的轮廓
            c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(c) > 500: # 过滤噪点
                # 计算中心矩
                M = cv2.moments(c)
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    return (cX, cY)
        return None

# --- 单元测试 (在家调试专用) ---
if __name__ == "__main__":
    # 使用笔记本摄像头测试逻辑
    cap = cv2.VideoCapture(0) 
    vision = VisionSystem()
    
    print(">>> 启动视觉仿真测试...")
    print(">>> 请拿一个深色物体(手机/鼠标)在摄像头前晃动")
    
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        processed_frame, offset = vision.process_frame(frame)
        
        if offset:
            print(f"\r检测到目标: 需移动 X={offset[0]:.1f}, Y={offset[1]:.1f}", end="")
            
        cv2.imshow("Vision Test (Home Mode)", processed_frame)
        if cv2.waitKey(1) == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()