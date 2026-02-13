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
# 格式：[H_min, S_min, V_min, H_max, S_max, V_max]
color_configs = {
    'red':    [0, 100, 80, 10, 255, 255],    # 红色
    'yellow': [20, 80, 80, 35, 255, 255],    # 黄色
    # 🥈 银色修改建议：提高 V_min (比如到 120)，只保留亮的，排除暗的
    'silver': [0, 0, 120, 180, 40, 255],     
    # 🖤 新增黑色：任意 H/S，但 V_max 必须很低 (比如低于 60)
    'black':  [0, 0, 0, 180, 255, 60]       
}

# 当前正在调试的颜色模式
current_mode = 'silver' # 默认先进银色调试，方便你看效果

# 窗口名称
WIN_MAIN = "Vision Calibration (Main)"
WIN_MASK = "Mask Preview"
WIN_CTRL = "Color Controls"

def nothing(x):
    pass

# 定义更新滑动条的辅助函数
def set_trackbars(values):
    cv2.setTrackbarPos('H Min', WIN_CTRL, int(values[0]))
    cv2.setTrackbarPos('S Min', WIN_CTRL, int(values[1]))
    cv2.setTrackbarPos('V Min', WIN_CTRL, int(values[2]))
    cv2.setTrackbarPos('H Max', WIN_CTRL, int(values[3]))
    cv2.setTrackbarPos('S Max', WIN_CTRL, int(values[4]))
    cv2.setTrackbarPos('V Max', WIN_CTRL, int(values[5]))

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

    # --- 右键：点击取色 (自动调整) ---
    elif event == cv2.EVENT_RBUTTONDOWN:
        if frame_hsv is not None:
            pixel = frame_hsv[y, x]
            h, s, v = pixel
            print(f"🔍 点击点 HSV: {pixel} (模式: {current_mode})")
            
            # 针对不同颜色的自动调整逻辑
            if current_mode == 'black':
                # 黑色策略：V_max 设为当前亮度 + 20，其他放宽
                new_vals = [0, 0, 0, 180, 255, min(255, v + 30)]
            elif current_mode == 'silver':
                # 银色策略：S_max 要低，V_min 要高
                new_vals = [0, 0, max(60, v - 40), 180, max(40, s + 20), 255]
            else:
                # 彩色策略
                new_vals = [
                    max(0, h - 10), max(0, s - 40), max(0, v - 40),
                    min(180, h + 10), min(255, s + 40), min(255, v + 40)
                ]
            
            set_trackbars(new_vals)

def save_config():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, 'config', 'vision_config.json')

    data = {
        "roi": current_roi if current_roi else [0, 0, 640, 480],
        "colors": {}
    }

    for color, vals in color_configs.items():
        # 兼容旧逻辑：把 min/max 拆开
        lower = [int(vals[0]), int(vals[1]), int(vals[2])]
        upper = [int(vals[3]), int(vals[4]), int(vals[5])]
        data["colors"][color] = [lower, upper]

    with open(config_path, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"💾 配置已保存至: {config_path}")
    print(f"   已保存颜色: {list(data['colors'].keys())}")

def main():
    global frame_hsv, current_mode, color_configs

    cv2.namedWindow(WIN_MAIN)
    cv2.setMouseCallback(WIN_MAIN, mouse_callback)
    cv2.namedWindow(WIN_MASK)
    cv2.namedWindow(WIN_CTRL)
    cv2.resizeWindow(WIN_CTRL, 400, 350)

    # 创建滑动条
    cv2.createTrackbar('H Min', WIN_CTRL, 0, 180, nothing)
    cv2.createTrackbar('S Min', WIN_CTRL, 0, 255, nothing)
    cv2.createTrackbar('V Min', WIN_CTRL, 0, 255, nothing)
    cv2.createTrackbar('H Max', WIN_CTRL, 0, 180, nothing)
    cv2.createTrackbar('S Max', WIN_CTRL, 0, 255, nothing)
    cv2.createTrackbar('V Max', WIN_CTRL, 0, 255, nothing)

    # 初始化滑动条
    set_trackbars(color_configs[current_mode])

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("="*50)
    print("🎨 视觉调试工具 (含黑色支持)")
    print("="*50)
    print("1. 🖱️ 左键: 画 ROI 区域")
    print("2. 🖱️ 右键: 点击画面物体自动吸色")
    print("3. ⌨️ 切换模式:")
    print("   [1] 红色  [2] 黄色")
    print("   [3] 银色 (调节 V Min 来排除黑色)")
    print("   [4] 黑色 (调节 V Max 来排除银色)")
    print("4. ⌨️ [S] 保存  [Q] 退出")
    print("="*50)

    while True:
        ret, frame = cap.read()
        if not ret: break

        frame_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        display = frame.copy()

        # 获取滑动条的值
        h_min = cv2.getTrackbarPos('H Min', WIN_CTRL)
        s_min = cv2.getTrackbarPos('S Min', WIN_CTRL)
        v_min = cv2.getTrackbarPos('V Min', WIN_CTRL)
        h_max = cv2.getTrackbarPos('H Max', WIN_CTRL)
        s_max = cv2.getTrackbarPos('S Max', WIN_CTRL)
        v_max = cv2.getTrackbarPos('V Max', WIN_CTRL)

        # 实时更新配置
        color_configs[current_mode] = [h_min, s_min, v_min, h_max, s_max, v_max]

        # 核心：计算 Mask
        lower = np.array([h_min, s_min, v_min])
        upper = np.array([h_max, s_max, v_max])
        
        # 只显示 ROI 区域的 Mask
        mask_full = np.zeros(frame.shape[:2], dtype="uint8")
        
        if current_roi:
            x, y, w, h = current_roi
            roi_hsv = frame_hsv[y:y+h, x:x+w]
            mask_roi = cv2.inRange(roi_hsv, lower, upper)
            mask_full[y:y+h, x:x+w] = mask_roi # 填回全图
            cv2.rectangle(display, (x, y), (x+w, y+h), (0, 255, 0), 2)
        else:
            mask_full = cv2.inRange(frame_hsv, lower, upper)

        # UI 显示
        info_text = f"MODE: {current_mode.upper()}"
        # 提示用户怎么调
        if current_mode == 'silver':
            hint = "Hint: Increase V-Min to exclude Black"
        elif current_mode == 'black':
            hint = "Hint: Decrease V-Max to exclude Silver"
        else:
            hint = ""
            
        cv2.putText(display, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(display, hint, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        cv2.imshow(WIN_MAIN, display)
        cv2.imshow(WIN_MASK, mask_full)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            save_config()
            break
        elif key == ord('1'):
            current_mode = 'red'
            set_trackbars(color_configs['red'])
        elif key == ord('2'):
            current_mode = 'yellow'
            set_trackbars(color_configs['yellow'])
        elif key == ord('3'):
            current_mode = 'silver'
            set_trackbars(color_configs['silver'])
        elif key == ord('4'):
            current_mode = 'black'
            set_trackbars(color_configs['black'])

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()