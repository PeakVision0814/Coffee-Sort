import cv2
import numpy as np
import glob
import os
import sys

# 将路径添加到 sys.path 以便保存配置
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- 配置参数 ---
# 棋盘格内角点数量 (行点数, 列点数) - 请数一下你打印的棋盘格交界点
CHECKERBOARD = (9, 6) 
# 每个格子的实际边长 (单位: mm) - 用尺子量一下打印出来的格子
SQUARE_SIZE = 25.0 
# 图片保存路径
IMG_DIR = "logs/calibration_imgs"
# 结果保存路径
CONFIG_FILE = "config/camera_matrix.npz"

def calibrate():
    # 1. 准备工作
    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR)
    
    # 定义世界坐标系中的点 (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
    objp = np.zeros((CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)
    objp = objp * SQUARE_SIZE

    # 用于存储所有图像的对象点和图像点
    objpoints = [] # 3d point in real world space
    imgpoints = [] # 2d points in image plane.

    # 2. 采集图像环节
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    print(f"=== 相机标定程序 ===")
    print(f"1. 请手持棋盘格，移动到摄像头视野内")
    print(f"2. 当看到画面中画出彩色角点时，按 's' 键保存")
    print(f"3. 请采集至少 15 张不同角度、远近的照片")
    print(f"4. 采集完成后，按 'q' 键开始计算")
    
    count = 0
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 寻找棋盘格角点
        ret_corners, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)

        # 用于显示的副本
        display_frame = frame.copy()

        if ret_corners:
            # 细化角点坐标 (亚像素级精度)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), 
                                        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
            # 画出来
            cv2.drawChessboardCorners(display_frame, CHECKERBOARD, corners2, ret_corners)
            
            # 显示当前采集数量
            cv2.putText(display_frame, f"Saved: {count}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow('Calibration', display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('s') and ret_corners:
            # 保存图片和点数据
            img_name = f"{IMG_DIR}/img_{count}.jpg"
            cv2.imwrite(img_name, frame)
            print(f"✅ 已保存: {img_name}")
            
            objpoints.append(objp)
            imgpoints.append(corners2)
            count += 1
            
        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    if count < 5:
        print("❌ 图片数量太少，无法标定。请至少拍摄 10 张以上。")
        return

    # 3. 计算内参矩阵
    print("\n⏳ 正在计算相机矩阵，请稍候...")
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)

    if ret:
        print("\n=== 标定成功！===")
        print(f"重投影误差 (越小越好): {ret:.4f}")
        print("内参矩阵 (Matrix):\n", mtx)
        print("畸变系数 (Dist):\n", dist)
        
        # 4. 保存结果
        if not os.path.exists("config"):
            os.makedirs("config")
        
        np.savez(CONFIG_FILE, mtx=mtx, dist=dist)
        print(f"\n💾 参数已保存至: {CONFIG_FILE}")
        print("后续的视觉程序将自动读取此文件进行画面矫正。")
    else:
        print("❌ 标定失败，请重试。")

if __name__ == "__main__":
    calibrate()