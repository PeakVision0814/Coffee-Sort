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

        # 2. 加载 ROI 配置文件 (这个依然需要，因为要划定检测区域)
        vision_config_path = os.path.join(self.config_dir, "vision_config.json")
        self.roi = None
        if os.path.exists(vision_config_path):
            with open(vision_config_path, 'r') as f:
                data = json.load(f)
                self.roi = data.get("roi") # [x, y, w, h]
                print(f"✅ [Vision] ROI 区域已加载: {self.roi}")
        else:
            print("⚠️ [Vision] 未找到 vision_config.json，请确保已圈定 ROI 区域")

        # 3. 颜色阈值 (红、黄、银)
        # 格式: 'color_name': [ (Lower_HSV, Upper_HSV), ... ]
        self.colors = {
            'red': [
                (np.array([0, 43, 46]), np.array([10, 255, 255])),
                (np.array([156, 43, 46]), np.array([180, 255, 255]))
            ],
            'yellow': [
                (np.array([11, 43, 46]), np.array([34, 255, 255]))
            ],
            'silver': [
                (np.array([0, 0, 46]), np.array([180, 40, 255]))
            ]
        }

    def process_frame(self, frame):
        """
        处理流程：绘制ROI -> 裁切 -> 颜色分析
        """
        # 🔥 彻底移除了去畸变 (cv2.undistort) 步骤，极大节省了系统算力！

        # 初始化结果容器
        result = {
            "detected": False,
            "color": "unknown",
            "offset": (0, 0) # 偏移量已弃用，保留结构以防上层报错
        }

        # 1. 如果没有 ROI，直接返回
        if not self.roi:
            cv2.putText(frame, "NO ROI CONFIG", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            return frame, result

        # 2. 绘制 ROI 框 (绿色矩形)
        x, y, w, h = self.roi
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(frame, "Detection Zone", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # 3. 核心逻辑：裁切 + 颜色分析
        roi_img = frame[y:y+h, x:x+w]
        
        # 转换到 HSV 空间
        hsv_roi = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
        hsv_roi = cv2.GaussianBlur(hsv_roi, (5, 5), 0)

        detected_color = None
        max_pixels = 0
        total_pixels = w * h
        
        # 阈值：颜色像素必须占 ROI 面积的 5% 以上
        pixel_threshold = total_pixels * 0.05 

        # 遍历颜色库
        for color_name, ranges in self.colors.items():
            mask = np.zeros(hsv_roi.shape[:2], dtype="uint8")
            
            for (lower, upper) in ranges:
                mask += cv2.inRange(hsv_roi, lower, upper)

            mask = cv2.erode(mask, None, iterations=2)
            mask = cv2.dilate(mask, None, iterations=2)

            count = cv2.countNonZero(mask)
            
            if count > pixel_threshold and count > max_pixels:
                max_pixels = count
                detected_color = color_name

        # 4. 更新结果
        if detected_color:
            result["detected"] = True
            result["color"] = detected_color
            
            # 在画面上显示结果
            text = f"Color: {detected_color.upper()}"
            (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            cv2.rectangle(frame, (x, y + h + 5), (x + text_w, y + h + 30), (0, 0, 0), -1)
            cv2.putText(frame, text, (x, y + h + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            
            # 画一个实心圆点表示识别中心
            cv2.circle(frame, (x + w//2, y + h//2), 8, (0, 255, 0), -1)

        return frame, result