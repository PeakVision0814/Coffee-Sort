from modules.vision import VisionSystem
from modules.arm_control import ArmController
import cv2
import time
import sys

def main():
    # 1. 初始化
    arm = ArmController()
    vision = VisionSystem()
    
    # 2. 机械臂就位
    arm.go_observe()
    
    # 3. 打开摄像头
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    # 设置分辨率确保清晰度
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    print("\n>>> 系统就绪！")
    print(">>> 操作说明：")
    print("    [空格键] -> 触发抓取 (Pick & Place)")
    print("    [  Q   ] -> 退出程序")
    print("    [  X   ] -> 点击窗口右上角关闭\n")
    
    # --- 关键修改：提前定义窗口名称 ---
    window_name = "Coffee Sorter Main View"
    cv2.namedWindow(window_name)

    while True:
        ret, frame = cap.read()
        if not ret: 
            time.sleep(0.1)
            continue
        
        # --- 关键修改：检测窗口是否被手动关闭 ---
        # 如果点击了 X，该属性通常会变成 -1 或 0
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            print("检测到窗口关闭，程序退出。")
            break

        # 视觉处理
        processed_frame, offset = vision.process_frame(frame)
        cv2.imshow(window_name, processed_frame)
        
        key = cv2.waitKey(1)
        
        # 按空格键 -> 执行一次抓取
        if key == 32: 
            if offset:
                print(f"\n🎯 锁定目标，偏差: {offset}")
                
                # 获取当前坐标
                current_coords = arm.mc.get_coords()
                if current_coords:
                    # 计算目标坐标 (当前 + 偏差)
                    target_x = current_coords[0] + offset[0]
                    target_y = current_coords[1] + offset[1]
                    
                    # 执行全套动作
                    arm.pick(target_x, target_y)
                    arm.place("A") # 默认放入 A 仓
                else:
                    print("⚠️ 无法读取当前机械臂坐标，取消抓取")
            else:
                print("👀 视野内未发现目标！")
        
        elif key == ord('q'):
            print("用户按键退出。")
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()