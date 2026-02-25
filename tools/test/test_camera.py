import cv2
import time

def test_camera_stream(camera_id=0):
    print(f"正在打开摄像头 (ID: {camera_id})...")
    
    # 1. 初始化摄像头
    cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
    
    # 设置分辨率
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("❌ 无法打开摄像头！请检查 USB 连接。")
        return

    print("✅ 摄像头已打开。")
    print("操作说明：")
    print("  - 按 'q' 键退出")
    print("  - 或直接点击窗口右上角 'X' 关闭")

    # 2. 关键修改：提前定义窗口名字，并手动创建窗口
    # 这样我们才能在循环里检查它是否还存在
    window_name = 'Camera Test'
    cv2.namedWindow(window_name)

    frame_count = 0
    start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            
            if not ret:
                print("⚠️ 警告：无法获取图像帧 (丢帧或断连)")
                time.sleep(0.5)
                continue

            # 3. 关键修改：检查窗口状态
            # getWindowProperty 获取窗口属性，WND_PROP_VISIBLE 表示窗口是否可见
            # 如果返回值 < 1，说明窗口被用户点击 X 关闭了
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                print("检测到窗口关闭，程序停止。")
                break

            # 计算帧率
            frame_count += 1
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # 显示画面
            cv2.imshow(window_name, frame)

            # 按 'q' 退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("用户按键退出。")
                break
                
    except KeyboardInterrupt:
        print("用户强制停止")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("摄像头资源已释放。")

if __name__ == "__main__":
    test_camera_stream(0)