# -*- coding: utf-8 -*-
# Copyright (c) 2026 Hangzhou Zhicheng Technology Co., Ltd. All rights reserved.
# 
# This code is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.
# 
# System: Coffee Intelligent Sorting System
# Author: Hangzhou Zhicheng Technology Co., Ltd
# modules\vision.py

import cv2
import numpy as np
import json
import os

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

        # 3. 加载 ROI 配置文件
        vision_config_path = os.path.join(self.config_dir, "vision_config.json")
        self.roi = None
        if os.path.exists(vision_config_path):
            with open(vision_config_path, 'r') as f:
                data = json.load(f)
                self.roi = data.get("roi") # [x, y, w, h]
                print(f"✅ [Vision] ROI 区域已加载: {self.roi}")
        else:
            print("⚠️ [Vision] 未找到 vision_config.json，请先运行 calibrate_vision.py")

        # 4. 🔥 核心修改：重新定义颜色阈值 (红、黄、银)
        # 格式: 'color_name': [ (Lower_HSV, Upper_HSV), ... ]
        # HSV范围: H(0-180), S(0-255), V(0-255)
        self.colors = {
            # 🔴 红色 (跨越 0 和 180，需要两个区间)
            'red': [
                (np.array([0, 43, 46]), np.array([10, 255, 255])),
                (np.array([156, 43, 46]), np.array([180, 255, 255]))
            ],
            
            # 🟡 金黄色 (Hue: 11-34, 涵盖橙黄到正黄)
            'yellow': [
                (np.array([11, 43, 46]), np.array([34, 255, 255]))
            ],

            # ⚪ 银色 (特殊：低饱和度 + 中高亮度)
            # 逻辑：只要饱和度(S)很低(<30)，且亮度(V)足够(>46)，就是银色/灰色
            'silver': [
                (np.array([0, 0, 46]), np.array([180, 40, 255]))
            ]
        }

    def process_frame(self, frame):
        """
        处理流程：去畸变 -> 绘制ROI -> 裁切 -> 颜色分析
        """
        # 1. 去畸变
        if self.mtx is not None:
            h, w = frame.shape[:2]
            newcameramtx, roi = cv2.getOptimalNewCameraMatrix(self.mtx, self.dist, (w,h), 1, (w,h))
            dst = cv2.undistort(frame, self.mtx, self.dist, None, newcameramtx)
            frame = dst

        # 初始化结果容器
        result = {
            "detected": False,
            "color": "unknown",
            "offset": (0, 0)
        }

        # 2. 如果没有 ROI，直接返回
        if not self.roi:
            cv2.putText(frame, "NO CONFIG", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            return frame, result

        # 3. 绘制 ROI 框 (绿色矩形)
        x, y, w, h = self.roi
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(frame, "Detection Zone", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # 4. 🔥 核心逻辑：裁切 + 颜色分析
        roi_img = frame[y:y+h, x:x+w]
        
        # 转换到 HSV 空间
        hsv_roi = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
        
        # 为了防止画面噪点（比如反光）造成的误判，进行简单的模糊处理
        hsv_roi = cv2.GaussianBlur(hsv_roi, (5, 5), 0)

        detected_color = None
        max_pixels = 0
        total_pixels = w * h
        
        # 阈值：颜色像素必须占 ROI 面积的 5% 以上才算识别成功
        # 银色可能需要更严格的阈值，防止背景误判
        pixel_threshold = total_pixels * 0.05 

        # 遍历颜色库
        for color_name, ranges in self.colors.items():
            mask = np.zeros(hsv_roi.shape[:2], dtype="uint8")
            
            # 合并该颜色的所有 HSV 区间
            for (lower, upper) in ranges:
                mask += cv2.inRange(hsv_roi, lower, upper)

            # 腐蚀与膨胀 (去除噪点)
            mask = cv2.erode(mask, None, iterations=2)
            mask = cv2.dilate(mask, None, iterations=2)

            # 统计符合颜色的像素点数量
            count = cv2.countNonZero(mask)
            
            # 调试用的：打印每个颜色看到的像素数 (可选)
            # print(f"Color: {color_name}, Pixels: {count}")

            # 找出像素最多且超过阈值的颜色
            if count > pixel_threshold and count > max_pixels:
                max_pixels = count
                detected_color = color_name

        # 5. 更新结果
        if detected_color:
            result["detected"] = True
            result["color"] = detected_color
            
            # 在画面上显示结果
            text = f"Color: {detected_color.upper()}"
            # 显示文字背景，让字更清晰
            (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            cv2.rectangle(frame, (x, y + h + 5), (x + text_w, y + h + 30), (0, 0, 0), -1)
            cv2.putText(frame, text, (x, y + h + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            
            # 画一个实心圆点表示识别中心
            cv2.circle(frame, (x + w//2, y + h//2), 8, (0, 255, 0), -1)

        return frame, result