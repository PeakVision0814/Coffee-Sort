# -*- coding: utf-8 -*-
# scripts/calibrate_vision.py

import cv2
import numpy as np
import json
import os

# --- 全局状态 ---
drawing = False
roi_start = (0, 0)
roi_end = (0, 0)
current_roi = None  # [x, y, w, h]

# 颜色配置缓存
# 默认值：[H_min, S_min, V_min, H_max, S_max, V_max]
color_configs = {
    'red':    [0, 100, 80, 10, 255, 255],    # 红色初始值
    'yellow': [20, 80, 80, 35, 255, 255],    # 黄色初始值
    'silver': [0, 0, 100, 180, 30, 255]      # 银色初始值 (低饱和度, 高亮度)
}

# 当前正在调试的颜色模式
current_mode = 'red' # red, yellow, silver

# 窗口名称
WIN_MAIN = "Vision Calibration (Main)"
WIN_MASK = "Mask Preview"
WIN_CTRL = "Color Controls"

def nothing(x):
    pass

def mouse_callback(event, x, y, flags, param):
    global drawing, roi_start, roi_end, current_roi, frame_hsv, color_configs, current_mode

    # --- 左键：画 ROI 框 ---
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        roi_start = (x, y)
        roi_end = (x, y)
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            roi_end = (x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        roi_end = (x, y)
        w = abs(roi_start[0] - roi_end[0])
        h = abs(roi_start[1] - roi_end[1])
        if w > 10 and h > 10:
            current_roi = [min(roi_start[0], roi_end[0]), min(roi_start[1], roi_end[1]), w, h]
            print(f"✅ ROI 更新: {current_roi}")

    # --- 右键：点击取色 (自动调整滑动条) ---
    elif event == cv2.EVENT_RBUTTONDOWN:
        if frame_hsv is not None:
            pixel = frame_hsv[y, x]
            h, s, v = pixel
            print(f"🔍 点击点 HSV: {pixel} -> 自动调整 '{current_mode}' 阈值")
            
            # 自动设置一个宽容度 (H±10, S±40, V±40)
            h_min = max(0, h - 10)
            h_max = min(180, h + 10)
            s_min = max(0, s - 40)
            s_max = min(255, s + 40)
            v_min = max(0, v - 40)
            v_max = min(255, v + 40)

            # 更新滑动条位置
            update_trackbars([h_min, s_min, v_min, h_max, s_max, v_max])

def update_trackbars(values):
    """更新滑动条位置"""
    cv2.setTrackbarPos('H Min', WIN_CTRL, int(values[0]))
    cv2.setTrackbarPos('S Min', WIN_CTRL, int(values[1]))
    cv2.setTrackbarPos('V Min', WIN_CTRL, int(values[2]))
    cv2.setTrackbarPos('H Max', WIN_CTRL, int(values[3]))
    cv2.setTrackbarPos('S Max', WIN_CTRL, int(values[4]))
    cv2.setTrackbarPos('V Max', WIN_CTRL, int(values[5]))

def save_config():
    if current_roi is None:
        print("❌ 无法保存: 请先画一个 ROI 框")
        return

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, 'config', 'vision_config.json')

    # 构造保存数据
    # 注意：为了让 vision.py 方便读取，我们需要把红色拆分成两个区间（如果它跨越了 0/180）
    # 但为了简化工具，这里我们保存原始的 min/max，由 vision.py 去处理逻辑
    data = {
        "roi": current_roi,
        "colors": {}
    }

    for color, vals in color_configs.items():
        # vals: [h_min, s_min, v_min, h_max, s_max, v_max]
        lower = [int(vals[0]), int(vals[1]), int(vals[2])]
        upper = [int(vals[3]), int(vals[4]), int(vals[5])]
        
        # 特殊处理红色：如果用户设置的 H_min 很小 (e.g. 0) 且 H_max 很大 (e.g. 180)，不做特殊处理
        # 但通常红色标定在 0-10 或 170-180。我们直接保存这个范围。
        # vision.py 会读取这个列表
        data["colors"][color] = [lower, upper]

    with open(config_path, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"💾 配置已保存至: {config_path}")
    print(f"   包含 ROI 和 颜色阈值: {list(data['colors'].keys())}")

def main():
    global frame_hsv, current_mode, color_configs

    # 初始化窗口
    cv2.namedWindow(WIN_MAIN)
    cv2.setMouseCallback(WIN_MAIN, mouse_callback)
    
    cv2.namedWindow(WIN_MASK)
    cv2.namedWindow(WIN_CTRL)
    cv2.resizeWindow(WIN_CTRL, 400, 300)

    # 创建滑动条
    def on_trackbar(val): pass
    cv2.createTrackbar('H Min', WIN_CTRL, 0, 180, on_trackbar)
    cv2.createTrackbar('S Min', WIN_CTRL, 0, 255, on_trackbar)
    cv2.createTrackbar('V Min', WIN_CTRL, 0, 255, on_trackbar)
    cv2.createTrackbar('H Max', WIN_CTRL, 0, 180, on_trackbar)
    cv2.createTrackbar('S Max', WIN_CTRL, 0, 255, on_trackbar)
    cv2.createTrackbar('V Max', WIN_CTRL, 0, 255, on_trackbar)

    # 初始化当前模式的滑动条
    update_trackbars(color_configs[current_mode])

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("="*50)
    print("🎨 高级颜色标定工具")
    print("1. 🖱️ 左键拖动: 画 ROI 框 (只在这个区域内识别)")
    print("2. ⌨️ 按键切换颜色模式:")
    print("   [1] 红色 (Red)")
    print("   [2] 黄色 (Yellow)")
    print("   [3] 银色 (Silver)")
    print("3. 🖱️ 右键点击: 点击画面中的物体，自动吸取颜色")
    print("4. 🎚️ 调整滑动条: 观察 Mask 窗口，直到只有目标物体变白")
    print("5. ⌨️ S 键: 保存并退出")
    print("="*50)

    while True:
        ret, frame = cap.read()
        if not ret: break

        frame_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        display = frame.copy()

        # 读取滑动条当前值
        h_min = cv2.getTrackbarPos('H Min', WIN_CTRL)
        s_min = cv2.getTrackbarPos('S Min', WIN_CTRL)
        v_min = cv2.getTrackbarPos('V Min', WIN_CTRL)
        h_max = cv2.getTrackbarPos('H Max', WIN_CTRL)
        s_max = cv2.getTrackbarPos('S Max', WIN_CTRL)
        v_max = cv2.getTrackbarPos('V Max', WIN_CTRL)

        # 更新内存中的配置
        color_configs[current_mode] = [h_min, s_min, v_min, h_max, s_max, v_max]

        # 生成掩膜 (Mask)
        lower = np.array([h_min, s_min, v_min])
        upper = np.array([h_max, s_max, v_max])
        
        # 针对 ROI 区域做 Mask 预览
        mask_display = np.zeros(frame.shape[:2], dtype="uint8")
        
        if current_roi:
            x, y, w, h = current_roi
            roi_img = frame_hsv[y:y+h, x:x+w]
            
            # 计算 mask
            mask_roi = cv2.inRange(roi_img, lower, upper)
            
            # 将 mask 放回全图位置方便观察
            mask_display[y:y+h, x:x+w] = mask_roi
            
            # 画框
            cv2.rectangle(display, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(display, f"ROI: {current_mode.upper()}", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            # 如果没画 ROI，全屏处理方便调试颜色
            mask_display = cv2.inRange(frame_hsv, lower, upper)
            if drawing:
                cv2.rectangle(display, roi_start, roi_end, (0, 255, 255), 2)

        # 显示
        cv2.putText(display, f"MODE: {current_mode.upper()}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.imshow(WIN_MAIN, display)
        cv2.imshow(WIN_MASK, mask_display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            save_config()
            break
        elif key == ord('q'):
            break
        # 模式切换
        elif key == ord('1'):
            current_mode = 'red'
            update_trackbars(color_configs['red'])
            print(f"👉 切换到: 红色调试")
        elif key == ord('2'):
            current_mode = 'yellow'
            update_trackbars(color_configs['yellow'])
            print(f"👉 切换到: 黄色调试")
        elif key == ord('3'):
            current_mode = 'silver'
            update_trackbars(color_configs['silver'])
            print(f"👉 切换到: 银色调试")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()