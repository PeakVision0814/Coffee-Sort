import cv2
import numpy as np
import json
import os

class VisionSystem:
    def __init__(self, config_dir="config"):
        # 1. 路径处理
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.config_dir = os.path.join(self.base_dir, config_dir)
        
        # 2. 加载相机内参 (保留，用于去畸变)
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

        # 3. 🔥 加载 ROI 配置文件 (你刚刚生成的那个文件)
        vision_config_path = os.path.join(self.config_dir, "vision_config.json")
        self.roi = None
        if os.path.exists(vision_config_path):
            with open(vision_config_path, 'r') as f:
                data = json.load(f)
                self.roi = data.get("roi") # [x, y, w, h]
                print(f"✅ [Vision] ROI 区域已加载: {self.roi}")
        else:
            print("⚠️ [Vision] 未找到 vision_config.json，请先运行 calibrate_vision.py")

        # 4. 🔥 定义颜色阈值 (在这里定义黄色)
        # 格式: [Lower HSV, Upper HSV]
        self.colors = {
            'red': [
                (np.array([0, 120, 70]), np.array([10, 255, 255])),
                (np.array([170, 120, 70]), np.array([180, 255, 255]))
            ],
            'blue': [
                (np.array([100, 150, 0]), np.array([140, 255, 255]))
            ],
            # 黄色通常在 20-35 之间
            'yellow': [
                (np.array([20, 100, 100]), np.array([35, 255, 255]))
            ]
        }

    def process_frame(self, frame):
        """
        新版处理流程：
        1. 去畸变
        2. 画出 ROI 框 (给人类看)
        3. 裁切 ROI 区域
        4. 分析颜色
        """
        # 1. 去畸变
        if self.mtx is not None:
            h, w = frame.shape[:2]
            newcameramtx, roi = cv2.getOptimalNewCameraMatrix(self.mtx, self.dist, (w,h), 1, (w,h))
            dst = cv2.undistort(frame, self.mtx, self.dist, None, newcameramtx)
            frame = dst

        # 结果容器
        result = {
            "detected": False,
            "color": "unknown",
            "offset": (0, 0) # 兼容旧接口，虽然现在不需要了
        }

        # 2. 如果没有 ROI，直接返回
        if not self.roi:
            cv2.putText(frame, "NO CONFIG", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            return frame, None

        # 3. 绘制 ROI 框 (绿色矩形)，方便调试
        x, y, w, h = self.roi
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(frame, "Detection Zone", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # 4. 🔥 核心逻辑：裁切 + 颜色分析
        roi_img = frame[y:y+h, x:x+w]
        hsv_roi = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
        
        detected_color = None
        max_pixels = 0
        total_pixels = w * h
        threshold = total_pixels * 0.05 # 必须占满 ROI 的 5% 才算有效

        # 遍历所有定义的颜色 (红、蓝、黄)
        for color_name, ranges in self.colors.items():
            mask = np.zeros(hsv_roi.shape[:2], dtype="uint8")
            
            # 处理颜色范围 (有的颜色像红色有两个区间，需要合并)
            if isinstance(ranges[0], tuple): 
                # 只有单个区间的 (如蓝、黄) - 这里的结构适配稍微调整一下以防万一
                # 上面的定义里 blue 和 yellow 我用的是 list 包裹 tuple，逻辑统一如下：
                 for (lower, upper) in ranges:
                    mask += cv2.inRange(hsv_roi, lower, upper)
            else:
                # 兼容旧写法
                 mask = cv2.inRange(hsv_roi, ranges[0], ranges[1])

            # 统计像素
            count = cv2.countNonZero(mask)
            
            # 找出像素最多的那个颜色
            if count > threshold and count > max_pixels:
                max_pixels = count
                detected_color = color_name

        # 5. 更新结果
        if detected_color:
            result["detected"] = True
            result["color"] = detected_color
            
            # 在画面上显示结果
            text = f"Color: {detected_color.upper()}"
            cv2.putText(frame, text, (x, y + h + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            
            # 画一个实心圆点表示识别到了
            cv2.circle(frame, (x + w//2, y + h//2), 10, (0, 255, 255), -1)

        # process_frame 约定返回 (处理后的图片, 结果数据)
        # 注意：这里第二个返回值改成了字典 result，而不是以前的 offset
        # 我们需要在 main.py 里适配这个变化
        return frame, result