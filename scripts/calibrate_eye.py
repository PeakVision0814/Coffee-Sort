import sys
import os
import time
import json
import cv2
import numpy as np

# 添加路径以导入模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from pymycobot import MyCobot280
except ImportError:
    print("请安装 pymycobot: pip install pymycobot")
    sys.exit(1)

# --- 配置 ---
PORT = "COM3"   # 请确认端口
BAUD = 115200
CAMERA_ID = 0
CONFIG_PATH = "config/calibration.json"

# 默认高度 (如果自动读取失败，将使用此值)
TEST_Z = 200 

def calibrate_eye():
    # 1. 连接设备
    print(">>> 连接机械臂...")
    try:
        mc = MyCobot280(PORT, BAUD)
        time.sleep(0.5)
        mc.power_on()
        time.sleep(1) # 等待上电稳定
    except Exception as e:
        print(f"机械臂连接失败: {e}")
        return

    # --- 进阶优化：自动读取当前 Z 轴高度 ---
    print(">>> 正在自动获取当前高度...")
    # 尝试读取 3 次，防止串口偶尔没数据
    current_coords = []
    for _ in range(3):
        current_coords = mc.get_coords()
        if current_coords:
            break
        time.sleep(0.1)

    if current_coords:
        global TEST_Z
        TEST_Z = current_coords[2] # 获取 Z 轴 (索引2)
        print(f"✅ 已锁定标定高度 Z = {TEST_Z:.2f} mm")
        print(f"   (当前姿态: {current_coords})")
    else:
        print(f"⚠️ 无法自动读取高度，将使用默认值 Z = {TEST_Z} mm")

    print("\n>>> 打开摄像头...")
    cap = cv2.VideoCapture(CAMERA_ID, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("无法打开摄像头")
        return

    # 2. 准备标定变量
    print("\n" + "="*50)
    print("   手眼标定程序 (Eye-in-Hand)   ")
    print("="*50)
    print(f"当前标定高度: {TEST_Z:.2f} mm (请保持此高度)")
    print("准备工作：")
    print("1. 在桌面上放一个固定参照物（如一枚硬币或画一个黑点）。")
    print("2. 确保相机能看清参照物。")
    print("3. 按键盘指令进行操作。")
    print("="*50 + "\n")

    # --- 关键修复：提前创建窗口 ---
    window_name = "Hand-Eye Calibration"
    cv2.namedWindow(window_name)
    
    # 辅助准星
    def draw_crosshair(img):
        h, w = img.shape[:2]
        cx, cy = w // 2, h // 2
        cv2.line(img, (cx - 20, cy), (cx + 20, cy), (0, 255, 0), 2)
        cv2.line(img, (cx, cy - 20), (cx, cy + 20), (0, 255, 0), 2)
        return cx, cy

    # 存储标定点
    points_recorded = {}
    
    print(">>> 步骤一：计算像素比例 (Scale)")
    print("请使用键盘 'w/s/a/d' 微调机械臂位置，使【相机中心】对准参照物。")
    print("对准后，按 '1' 确认基准点。")

    while True:
        ret, frame = cap.read()
        if not ret: 
            time.sleep(0.1)
            continue
        
        # --- 关键修复：检测窗口是否被关闭 ---
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            print("检测到窗口关闭，程序停止。")
            cap.release()
            return # 直接结束程序

        draw_crosshair(frame)
        
        # 显示提示信息
        info = "Step 1: Center Camera over target"
        if 'p1' in points_recorded:
            info = "Step 2: Move X+ 20mm, then press '2'"
        
        cv2.putText(frame, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imshow(window_name, frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        # 键盘退出
        if key == ord('q') or key == 27: # q 或 ESC
            print("用户取消操作。")
            cap.release()
            cv2.destroyAllWindows()
            return

        # 键盘控制机械臂微调 (方便对准)
        coords = mc.get_coords()
        if not coords: continue
        step = 2 # 微调步长 2mm
        
        if key == ord('w'): mc.send_coord(1, coords[0] + step, 50) # X+
        elif key == ord('s'): mc.send_coord(1, coords[0] - step, 50) # X-
        elif key == ord('a'): mc.send_coord(2, coords[1] + step, 50) # Y+ (注意方向可能反)
        elif key == ord('d'): mc.send_coord(2, coords[1] - step, 50) # Y-
        
        # 记录点位
        elif key == ord('1'):
            # 记录中心点 (图像中心 320, 240)
            points_recorded['p1'] = {'coords': coords, 'pixel': (320, 240)} 
            print(f"✅ 基准点 P1 已记录: {coords}")
            print(">>> 请控制机械臂沿 X 轴正方向移动约 20mm (按 'w')")
            print(">>> 移动后，不要动参照物，观察参照物在画面中的新位置，按 '2' 记录")
            
        elif key == ord('2') and 'p1' in points_recorded:
            print("❄️ 画面已冻结，请用鼠标点击画面中的参照物中心！")
            
            ref_pixel = []
            def on_click(event, x, y, flags, param):
                if event == cv2.EVENT_LBUTTONDOWN:
                    ref_pixel.append((x, y))
            
            cv2.setMouseCallback(window_name, on_click)
            
            while not ref_pixel:
                # 在冻结等待点击期间，也要检测窗口关闭
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    print("检测到窗口关闭，程序停止。")
                    cap.release()
                    return
                
                cv2.imshow(window_name, frame)
                if cv2.waitKey(1) == 27: break # ESC
            
            points_recorded['p2'] = {'coords': coords, 'pixel': ref_pixel[0]}
            print(f"✅ 偏移点 P2 已记录: 机械臂{coords}, 像素{ref_pixel[0]}")
            break

    # 计算比例
    p1 = points_recorded['p1']
    p2 = points_recorded['p2']
    
    # 物理距离 (mm)
    dist_mm_x = p2['coords'][0] - p1['coords'][0]
    dist_mm_y = p2['coords'][1] - p1['coords'][1]
    dist_mm = np.sqrt(dist_mm_x**2 + dist_mm_y**2)
    
    # 像素距离 (pixel)
    dist_px_x = p2['pixel'][0] - p1['pixel'][0]
    dist_px_y = p2['pixel'][1] - p1['pixel'][1]
    dist_px = np.sqrt(dist_px_x**2 + dist_px_y**2)
    
    if dist_px == 0:
        print("❌ 错误：像素未发生移动，请重试")
        cap.release()
        return

    scale = dist_mm / dist_px # mm per pixel
    print(f"\n📊 计算结果：1 像素 ≈ {scale:.4f} mm")
    
    # 3. 计算夹爪中心与相机中心偏移
    print("\n>>> 步骤二：计算夹爪偏移 (Gripper Offset)")
    print("1. 请移动机械臂，使【夹爪中心】垂直对准刚才那个参照物。")
    print("   (你可以拿一根笔插在夹爪中间辅助对准)")
    print("2. 对准后，按 '3' 确认。")
    
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        # --- 关键修复：检测窗口是否被关闭 ---
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            print("检测到窗口关闭，程序停止。")
            cap.release()
            return

        cv2.imshow(window_name, frame)
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'): 
            cap.release()
            cv2.destroyAllWindows()
            return

        # 依然可以用键盘微调
        coords = mc.get_coords()
        if key == ord('w'): mc.send_coord(1, coords[0] + 2, 50)
        elif key == ord('s'): mc.send_coord(1, coords[0] - 2, 50)
        elif key == ord('a'): mc.send_coord(2, coords[1] + 2, 50)
        elif key == ord('d'): mc.send_coord(2, coords[1] - 2, 50)
        
        elif key == ord('3'):
            gripper_pos = coords
            camera_pos = p1['coords'] # P1 是相机对准参照物时的机械臂坐标
            
            # 偏移量 = 夹爪对准时的坐标 - 相机对准时的坐标
            offset_x = gripper_pos[0] - camera_pos[0]
            offset_y = gripper_pos[1] - camera_pos[1]
            
            print(f"✅ 偏移已记录: X轴偏 {offset_x:.2f}mm, Y轴偏 {offset_y:.2f}mm")
            break

    # 4. 保存结果
    calibration_data = {
        "scale_mm_per_pixel": scale,
        "camera_gripper_offset": [offset_x, offset_y],
        "calibrate_height": TEST_Z,
        "camera_matrix_path": "config/camera_matrix.npz"
    }
    
    # 确保 config 目录存在
    if not os.path.exists("config"):
        os.makedirs("config")

    with open(CONFIG_PATH, 'w') as f:
        json.dump(calibration_data, f, indent=4)
        
    print(f"\n💾 标定参数已保存至: {CONFIG_PATH}")
    print("🎉 恭喜！手眼标定完成。")
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    calibrate_eye()