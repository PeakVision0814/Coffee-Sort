import cv2
import numpy as np
import json
import os

# --- 全局变量 ---
drawing = False
roi_start = (0, 0)
roi_end = (0, 0)
current_roi = None # 格式: (x, y, w, h)

# 颜色阈值字典 (开发阶段先用大概范围，后续可以通过右键点击精确调整)
# 格式: 'color_name': [lower_hsv, upper_hsv]
color_ranges = {
    'red':   [np.array([0, 120, 70]), np.array([10, 255, 255])],     # 红色通常在 0-10 和 170-180
    'red2':  [np.array([170, 120, 70]), np.array([180, 255, 255])],  # 红色的另一端
    'blue':  [np.array([100, 150, 0]), np.array([140, 255, 255])],   # 蓝色范围
    'green': [np.array([40, 70, 70]), np.array([80, 255, 255])],      # 绿色范围
    'yellow': [np.array([20, 100, 100]), np.array([35, 255, 255])]
}

def mouse_callback(event, x, y, flags, param):
    global drawing, roi_start, roi_end, current_roi, frame_hsv

    # --- 左键拖动：画 ROI 框 ---
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
        # 计算 ROI (x, y, w, h)
        x_min = min(roi_start[0], roi_end[0])
        y_min = min(roi_start[1], roi_end[1])
        w = abs(roi_start[0] - roi_end[0])
        h = abs(roi_start[1] - roi_end[1])
        if w > 10 and h > 10:
            current_roi = (x_min, y_min, w, h)
            print(f"✅ ROI 已设定: {current_roi}")
        else:
            print("⚠️ 区域太小，已忽略")

    # --- 右键点击：取色 (帮你分析贴纸颜色) ---
    elif event == cv2.EVENT_RBUTTONDOWN:
        if frame_hsv is not None:
            pixel = frame_hsv[y, x]
            print(f"🔍 坐标({x},{y}) 的 HSV 值: {pixel}")
            print(f"   提示: Hue(色相)={pixel[0]}, Sat(饱和度)={pixel[1]}, Val(亮度)={pixel[2]}")

def save_config():
    if current_roi is None:
        print("❌ 无法保存: 请先画一个 ROI 框")
        return

    # 路径回退一级到根目录，再进 config
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, 'config', 'vision_config.json')

    data = {
        "roi": current_roi, # [x, y, w, h]
        # 这里仅保存 ROI，颜色阈值通常写在代码里或者高级配置里，
        # 但为了演示，我们也可以把颜色配置留个接口
        "color_mode": "hsv" 
    }
    
    with open(config_path, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"💾 配置已保存至: {config_path}")

def main():
    global frame_hsv
    
    # 尝试打开摄像头
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("❌ 无法打开摄像头")
        return

    cv2.namedWindow("Calibration")
    cv2.setMouseCallback("Calibration", mouse_callback)

    print("="*50)
    print("🎥 视觉标定工具 v1.0")
    print("🖱️  左键拖动: 框选盒子出现的固定区域 (ROI)")
    print("🖱️  右键点击: 查看像素点的 HSV 颜色值 (用于调试阈值)")
    print("⌨️  S 键: 保存配置并退出")
    print("⌨️  Q 键: 不保存退出")
    print("="*50)

    while True:
        ret, frame = cap.read()
        if not ret: break

        # 转换 HSV 用于取色分析
        frame_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        display = frame.copy()

        # 1. 绘制正在画的框
        if drawing:
            cv2.rectangle(display, roi_start, roi_end, (0, 255, 255), 2)
        
        # 2. 绘制已确定的 ROI
        if current_roi:
            x, y, w, h = current_roi
            cv2.rectangle(display, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(display, "ROI Area", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # --- 实时预览：在这个 ROI 里找颜色 ---
            # 这是一个简单的预览，看看能不能识别出红色
            roi_img = frame_hsv[y:y+h, x:x+w]
            
            # 检测红色 (合并两个红色区间)
            mask1 = cv2.inRange(roi_img, color_ranges['red'][0], color_ranges['red'][1])
            mask2 = cv2.inRange(roi_img, color_ranges['red2'][0], color_ranges['red2'][1])
            mask_red = mask1 + mask2
            
            # 检测蓝色
            mask_blue = cv2.inRange(roi_img, color_ranges['blue'][0], color_ranges['blue'][1])

            # 检测黄色
            mask_yellow = cv2.inRange(roi_img, color_ranges['yellow'][0], color_ranges['yellow'][1])

            # 统计像素点
            red_pixels = cv2.countNonZero(mask_red)
            blue_pixels = cv2.countNonZero(mask_blue)
            yellow_pixels = cv2.countNonZero(mask_yellow) # 🔥 统计黄色像素

            total_pixels = w * h

            # 简单的判断逻辑 (如果红色像素超过 5% 就认为是红色)
            detected_color = "None"
            color_bgr = (200, 200, 200)

            threshold = total_pixels * 0.05

            if red_pixels > threshold:
                detected_color = "RED"
                color_bgr = (0, 0, 255)
            elif blue_pixels > threshold:
                detected_color = "BLUE"
                color_bgr = (255, 0, 0)
            elif yellow_pixels > threshold: # 🔥 新增判断
                detected_color = "YELLOW"
                color_bgr = (0, 255, 255) # 黄色的 BGR 显示颜色 (Cyan)
            
            # 在 ROI 中心显示识别结果
            cv2.putText(display, detected_color, (x+10, y+h//2), cv2.FONT_HERSHEY_SIMPLEX, 1, color_bgr, 3)

        cv2.imshow("Calibration", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            save_config()
            break
        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()