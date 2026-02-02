from modules.vision import VisionSystem
from modules.arm_control import ArmController
import cv2
import time

def main():
    # 1. 初始化
    arm = ArmController()
    vision = VisionSystem()

    # 2. 去观测点
    arm.go_observe()

    # 3. 打开摄像头
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    print(">>> 系统就绪，按下 'SPACE' 键触发抓取！")

    while True:
        ret, frame = cap.read()
        if not ret: continue

        # 视觉处理
        processed_frame, offset = vision.process_frame(frame)
        cv2.imshow("Main View", processed_frame)

        key = cv2.waitKey(1)

        # 按空格键 -> 执行一次抓取
        if key == 32: 
            if offset:
                print(f"检测到目标，偏差: {offset}")

                # --- 核心坐标计算 ---
                # 目标 X = 当前 X + 视觉偏差 X
                # 目标 Y = 当前 Y + 视觉偏差 Y
                # 注意：这里需要你明天获取一下当前观测点的绝对坐标
                current_coords = arm.mc.get_coords()
                target_x = current_coords[0] + offset[0] # 注意方向！
                target_y = current_coords[1] + offset[1]

                # 执行抓取
                arm.pick(target_x, target_y)
                arm.place("A")

                # 抓完回来继续看
                arm.go_observe()
            else:
                print("没看到东西！")

        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()