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

# --- 配置 ---
PORT = settings.PORT
BAUD = settings.BAUD

def print_instructions():
    print("\n" + "="*50)
    print("🎮 机械臂全能微调助手 (Fine-Tuning Pro)")
    print("="*50)
    print("  [ J / L ]  -> J1 (底座左右)")
    print("  [ I / K ]  -> J2 (大臂前后)")
    print("  [ U / O ]  -> J3 (小臂升降)")
    print("  [ Y / H ]  -> J4 (点头微调)")
    print("  [ T / G ]  -> J5 (手腕水平)")
    print("  [ R / F ]  -> J6 (爪子旋转) <--- 新增")
    print("-------------------------------------")
    print("  [ 1 / 2 ]  -> 切换精度 (0.5度 / 2.0度)")
    print("  [ SPACE ]  -> ✅ 打印结果 (复制到 settings.py)")
    print("  [ Q ]      -> 退出")
    print("="*50 + "\n")

def main():
    try:
        mc = MyCobot280(PORT, BAUD)
        time.sleep(0.5)
        mc.power_on()
        print(f"✅ 连接成功: {PORT}")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    # --- 1. 选择菜单 (14个点位) ---
    print("\n请选择要微调的目标:")
    print("--- 抓取区 ---")
    print(" 1. 抓取点 (Grab - Low)")
    print(" 2. 抓取观测点 (Observe - High)")
    print("--- 放置区 ---")
    print(" 3. 1号槽位 - 放下 (Low)")
    print(" 4. 1号槽位 - 观察 (High)")
    print(" 5. 2号槽位 - 放下 (Low)")
    print(" 6. 2号槽位 - 观察 (High)")
    print(" 7. 3号槽位 - 放下 (Low)")
    print(" 8. 3号槽位 - 观察 (High)")
    print(" 9. 4号槽位 - 放下 (Low)")
    print("10. 4号槽位 - 观察 (High)")
    print("11. 5号槽位 - 放下 (Low)")
    print("12. 5号槽位 - 观察 (High)")
    print("13. 6号槽位 - 放下 (Low)")
    print("14. 6号槽位 - 观察 (High)")
    
    choice_str = input("\n请输入数字 (1-14): ").strip()
    if not choice_str.isdigit():
        print("❌ 输入无效")
        return
        
    choice = int(choice_str)
    
    target_angles = []
    target_name = "" # 用于打印提示

    # 逻辑映射
    if choice == 1:
        target_angles = settings.PICK_POSES['grab']
        target_name = 'PICK_POSES["grab"]'
    elif choice == 2:
        target_angles = settings.PICK_POSES['observe']
        target_name = 'PICK_POSES["observe"]'
    elif 3 <= choice <= 14:
        # 计算槽位ID和类型
        # 3,4 -> Slot 1
        # 5,6 -> Slot 2
        offset_idx = choice - 3
        slot_id = (offset_idx // 2) + 1
        is_high = (offset_idx % 2) == 1 # 偶数是Low, 奇数是High
        
        rack = settings.STORAGE_RACKS[slot_id]
        if is_high:
            target_angles = rack['high']
            target_name = f'STORAGE_RACKS[{slot_id}]["high"]'
        else:
            target_angles = rack['low']
            target_name = f'STORAGE_RACKS[{slot_id}]["low"]'
    else:
        print("❌ 无效选择")
        return

    print(f"🚀 前往: {target_name}")
    print(f"   初始角度: {target_angles}")
    mc.send_angles(target_angles, 50)
    time.sleep(2)

    # --- 2. 微调循环 ---
    window_name = "Fine Tune Pro (Focus Here)"
    cv2.namedWindow(window_name)
    print_instructions()

    current_angles = copy.deepcopy(target_angles)
    step = 1.0 

    while True:
        # 生成黑色背景
        img = np.zeros((400, 600, 3), dtype=np.uint8)
        
        # 显示信息
        cv2.putText(img, f"Target: {target_name}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(img, f"Angles: {[round(a, 1) for a in current_angles]}", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv2.putText(img, f"Step: {step} deg", (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
        # 简单的操作指引
        help_text = [
            "Keys:",
            "J/L: Base(J1)   I/K: Arm(J2)",
            "U/O: Arm(J3)    Y/H: Head(J4)",
            "T/G: Wrist(J5)  R/F: Rot(J6)",
            "SPACE: Save     Q: Quit"
        ]
        for i, text in enumerate(help_text):
            cv2.putText(img, text, (10, 200 + i*30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        cv2.imshow(window_name, img)

        key = cv2.waitKey(50) & 0xFF
        changed = False
        
        # --- 按键映射 ---
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
        
        # 🔥 新增 J6 控制
        elif key == ord('r'): current_angles[5] += step; changed=True
        elif key == ord('f'): current_angles[5] -= step; changed=True

        elif key == ord('1'): step = 0.5
        elif key == ord('2'): step = 2.0

        elif key == 32: # Space
            print("\n" + "*"*60)
            print(f"✨ 替换 {target_name} 的数据为:")
            # 格式化输出
            print(f"{[round(x, 2) for x in current_angles]}")
            print("*"*60 + "\n")
        
        elif key == ord('q'):
            break
            
        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            break

        if changed:
            mc.send_angles(current_angles, 80)
            print(f"调整 -> J1..J6: {[round(x,1) for x in current_angles]}")

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()