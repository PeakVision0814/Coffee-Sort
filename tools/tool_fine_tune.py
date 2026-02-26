# -*- coding: utf-8 -*-
# scripts/tool_finetune.py

import sys
import os
import time
import cv2
import copy
import numpy as np

# 路径处理
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from pymycobot import MyCobot280
    from config import settings
except ImportError:
    print("❌ 无法导入项目模块")
    sys.exit(1)

PORT = settings.PORT
BAUD = settings.BAUD
GPIO_GRIPPER = getattr(settings, 'GPIO_GRIPPER', 2)

def main():
    try:
        print(f"正在连接机械臂 ({PORT})...")
        mc = MyCobot280(PORT, BAUD)
        time.sleep(0.5)
        mc.power_on()
        print("✅ 连接成功！")
        mc.set_basic_output(GPIO_GRIPPER, 0)
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened(): print("⚠️ 无摄像头")

    # --- 菜单逻辑 ---
    print("\n" + "="*40)
    print("   🎯 三点式微调助手 (High -> Mid -> Low)")
    print("="*40)
    print("--- 抓取区 ---")
    print(" 1. 抓取点 (Low)")
    print(" 2. 过渡点 (Mid)")
    print(" 3. 观测点 (High)")
    print("--- 放置区 ---")
    print(" 4. 1号 Low   5. 1号 Mid   6. 1号 High")
    print(" 7. 2号 Low   8. 2号 Mid   9. 2号 High")
    print("10. 3号 Low  11. 3号 Mid  12. 3号 High")
    print("13. 4号 Low  14. 4号 Mid  15. 4号 High")
    print("16. 5号 Low  17. 5号 Mid  18. 5号 High")
    print("19. 6号 Low  20. 6号 Mid  21. 6号 High")
    
    choice_str = input("\n请输入数字 (1-21): ").strip()
    if not choice_str.isdigit(): return
    choice = int(choice_str)
    
    target_angles = []
    target_name = "" 

    try:
        if choice == 1:
            target_angles = settings.PICK_POSES['grab']
            target_name = 'PICK["grab"]'
        elif choice == 2:
            target_angles = settings.PICK_POSES['mid']
            target_name = 'PICK["mid"]'
        elif choice == 3:
            target_angles = settings.PICK_POSES['observe']
            target_name = 'PICK["observe"]'
        elif 4 <= choice <= 21:
            offset = choice - 4
            slot_id = (offset // 3) + 1
            pos_type_idx = offset % 3 
            rack = settings.STORAGE_RACKS[slot_id]
            
            type_map = {0: "low", 1: "mid", 2: "high"}
            p_type = type_map[pos_type_idx]
            
            target_angles = rack[p_type]
            target_name = f'RACK[{slot_id}]["{p_type}"]'
        else:
            print("❌ 无效选择")
            return
    except KeyError:
        print(f"❌ 缺少键值: {target_name}，请先在 settings.py 补全结构！")
        return

    print(f"🚀 前往目标: {target_name}")
    mc.send_angles(target_angles, 50)
    time.sleep(2)

    # --- 微调循环 ---
    window_name = "Fine-Tuner V3 (Mid Support)"
    cv2.namedWindow(window_name)

    current_angles = copy.deepcopy(target_angles)
    step = 1.0 
    gripper_state = "Open (0)"
    servo_state = "Locked"

    while True:
        if cap.isOpened():
            ret, frame = cap.read()
            if not ret: frame = np.zeros((480, 640, 3), dtype=np.uint8)
        else:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        frame = cv2.resize(frame, (640, 480))
        h, w = frame.shape[:2]

        # 右侧 HUD 背景
        overlay = frame.copy()
        cv2.rectangle(overlay, (w - 260, 0), (w, h), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
        
        # 文字起始位置
        x_base = w - 250 

        # --- 1. 顶部信息 ---
        cv2.putText(frame, "TARGET:", (x_base, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(frame, target_name, (x_base, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        cv2.putText(frame, "ANGLES:", (x_base, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        for i, ang in enumerate(current_angles):
            txt = f"J{i+1}: {ang:.1f}"
            cv2.putText(frame, txt, (x_base, 95 + i*18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 255, 200), 1)

        # --- 2. 状态信息 ---
        y_status = 215
        cv2.putText(frame, f"STEP: {step}", (x_base, y_status), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
        
        g_color = (0, 255, 0) if "Open" in gripper_state else (0, 0, 255)
        cv2.putText(frame, f"GRIP: {gripper_state}", (x_base, y_status + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, g_color, 2)
        
        s_color = (0, 255, 0) if "Lock" in servo_state else (0, 0, 255)
        cv2.putText(frame, f"SERVO: {servo_state}", (x_base, y_status + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, s_color, 2)

        # --- 3. 按键说明 (这次加上了!) ---
        y_help = 290
        help_lines = [
            "----------------",
            "[9] Unlock  [0] Lock",
            "[Z] Open    [X] Close",
            "----------------",
            "[J/L] J1  [I/K] J2",
            "[U/O] J3  [Y/H] J4",
            "[T/G] J5  [R/F] J6",
            "----------------",
            "[1/2] Step Change",
            "[SPACE] Save Data",
            "[Q] Quit"
        ]
        
        for i, line in enumerate(help_lines):
            # 字体改小一点 (0.45) 确保放得下
            cv2.putText(frame, line, (x_base, y_help + i*16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

        # 辅助线
        cv2.line(frame, (w//2 - 20, h//2), (w//2 + 20, h//2), (0, 255, 0), 1)
        cv2.line(frame, (w//2, h//2 - 20), (w//2, h//2 + 20), (0, 255, 0), 1)

        cv2.imshow(window_name, frame)
        key = cv2.waitKey(10) & 0xFF
        
        changed = False
        allow_move = "Lock" in servo_state

        if allow_move:
            if key == ord('j'):   current_angles[0] += step; changed=True
            elif key == ord('l'): current_angles[0] -= step; changed=True
            elif key == ord('i'): current_angles[1] += step; changed=True
            elif key == ord('k'): current_angles[1] -= step; changed=True
            elif key == ord('u'): current_angles[2] += step; changed=True
            elif key == ord('o'): current_angles[2] -= step; changed=True
            elif key == ord('y'): current_angles[3] += step; changed=True
            elif key == ord('h'): current_angles[3] -= step; changed=True
            elif key == ord('t'): current_angles[4] += step; changed=True
            elif key == ord('g'): current_angles[4] -= step; changed=True
            elif key == ord('r'): current_angles[5] += step; changed=True
            elif key == ord('f'): current_angles[5] -= step; changed=True

        # 功能键
        if key == ord('9'): 
            mc.release_all_servos()
            servo_state = "Release"
            print(">>> 🔓 Unlocked")
        elif key == ord('0'): 
            mc.power_on()
            time.sleep(0.1)
            new_angles = mc.get_angles()
            if new_angles: current_angles = new_angles
            servo_state = "Locked"
            print(">>> 🔒 Locked & Synced")

        elif key == ord('z'): 
            mc.set_basic_output(GPIO_GRIPPER, 0)
            gripper_state = "Open"
        elif key == ord('x'): 
            mc.set_basic_output(GPIO_GRIPPER, 1)
            gripper_state = "Close"

        elif key == ord('1'): step = 0.5
        elif key == ord('2'): step = 2.0

        elif key == 32: # Space
            print("\n" + "*"*60)
            print(f"✨ 替换 {target_name} 的数据为:")
            print(f"{[round(x, 2) for x in current_angles]}")
            print("*"*60 + "\n")
            cv2.putText(frame, "SAVED!", (50, h//2), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 255), 3)
            cv2.imshow(window_name, frame)
            cv2.waitKey(300)
        
        elif key == ord('q'): break
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1: break

        if changed and allow_move:
            mc.send_angles(current_angles, 80)

    if cap.isOpened(): cap.release()
    cv2.destroyAllWindows()
    try: mc.set_basic_output(GPIO_GRIPPER, 0)
    except: pass

if __name__ == "__main__":
    main()