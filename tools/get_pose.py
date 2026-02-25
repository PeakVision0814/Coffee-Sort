# tools/get_pose.py
import time
import cv2
import numpy as np
import sys
import os

# 将项目根目录加入环境变量
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from config import settings

try:
    from pymycobot import MyCobot280
except ImportError:
    from pymycobot import MyCobot as MyCobot280

print("🔌 正在连接真实机械臂...")
mc = MyCobot280(settings.PORT, settings.BAUD)
time.sleep(1)
if not mc.is_power_on():
    mc.power_on()

# ================= 全局状态 =================
is_released = False
locked_angles = [0.0] * 6  # 锁定时的基准角度，用于微调
current_task_idx = 0
results = {}

# 🔥 新增：启动时预加载 settings.py 中的已有数据 (编辑模式)
print("📂 正在从 settings.py 加载历史标定数据...")
if hasattr(settings, 'PICK_POSES'):
    for k in ["observe", "mid", "grab"]:
        if k in settings.PICK_POSES: 
            results[f"PICK_{k}"] = settings.PICK_POSES[k]

if hasattr(settings, 'STORAGE_RACKS'):
    for i in range(1, 7):
        rack = settings.STORAGE_RACKS.get(i, {})
        for k in ["high", "mid", "low"]:
            if k in rack: 
                results[f"SLOT_{i}_{k}"] = rack[k]

# 定义21个任务点
TASKS = [
    ("PICK", "observe", "抓取区-High"),
    ("PICK", "mid",     "抓取区-Mid"),
    ("PICK", "grab",    "抓取区-Low"),
]
for i in range(1, 7):
    TASKS.append((f"SLOT_{i}", "high", f"槽位{i}-High"))
    TASKS.append((f"SLOT_{i}", "mid",  f"槽位{i}-Mid"))
    TASKS.append((f"SLOT_{i}", "low",  f"槽位{i}-Low"))

# ================= UI 与按钮定义 =================
BUTTONS = []
start_x, start_y = 30, 150
btn_w, btn_h = 120, 40
x_gap, y_gap = 140, 60

# 生成抓取区按钮
for i in range(3):
    BUTTONS.append({"rect": (start_x, start_y + i*y_gap, btn_w, btn_h), "idx": i})

# 生成槽位按钮
for slot in range(6):
    for point in range(3):
        idx = 3 + slot * 3 + point
        bx = start_x + (slot + 1) * x_gap
        by = start_y + point * y_gap
        BUTTONS.append({"rect": (bx, by, btn_w, btn_h), "idx": idx})

def mouse_callback(event, x, y, flags, param):
    global current_task_idx
    if event == cv2.EVENT_LBUTTONDOWN:
        for btn in BUTTONS:
            bx, by, bw, bh = btn["rect"]
            if bx <= x <= bx + bw and by <= y <= by + bh:
                current_task_idx = btn["idx"]
                print(f"\n👉 已选中: 【{TASKS[current_task_idx][2]}】 (可按 M 键前往该点)")
                break

cv2.namedWindow("Pro Calibration Teach Pendant")
cv2.setMouseCallback("Pro Calibration Teach Pendant", mouse_callback)

# ================= 核心控制函数 =================
def toggle_motors():
    global is_released, locked_angles
    if is_released:
        angles = mc.get_angles()
        if angles:
            locked_angles = [round(a, 2) for a in angles]
            mc.send_angles(locked_angles, 50)
        print("\n🔒 [已锁定] 机械臂固定。可以使用键盘微调角度了。")
        is_released = False
    else:
        mc.release_all_servos()
        print("\n🟢 [已释放] 电机已释放，可自由拖拽...")
        is_released = True

def adjust_joint(joint_idx, delta):
    global locked_angles, is_released
    if is_released:
        print("\n⚠️ 请先按空格【锁定】电机，再进行微调！")
        return
    locked_angles[joint_idx] += delta
    locked_angles[joint_idx] = round(locked_angles[joint_idx], 2)
    mc.send_angles(locked_angles, 20)
    print(f"\r微调 J{joint_idx+1} -> {locked_angles[joint_idx]} | 当前整体: {locked_angles}", end="")

def control_gripper(state):
    try:
        mc.set_basic_output(settings.GPIO_GRIPPER, state)
        action = "闭合" if state == 1 else "张开"
        print(f"\n🖐️ 气爪已{action}")
    except Exception as e:
        print(f"\n⚠️ 气爪控制异常: {e}")

# 初始释放
toggle_motors()
canvas = np.zeros((450, 1050, 3), dtype=np.uint8)

try:
    while True:
        angles = mc.get_angles()
        coords = mc.get_coords()
        
        # 增加容错：确保读到的是真正的列表
        if not isinstance(angles, list): angles = None
        if not isinstance(coords, list): coords = None
        
        z_height = coords[2] if (coords and len(coords) >= 3) else 0.0
        
        # --- UI 绘制 ---
        canvas.fill(30)
        
        status_txt = "Status: RELEASED (Drag freely)" if is_released else "Status: LOCKED (Use keys to fine-tune)"
        status_color = (0, 255, 0) if is_released else (0, 0, 255)
        cv2.putText(canvas, status_txt, (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
        cv2.putText(canvas, f"Z_Height: {z_height:>6.1f} mm", (400, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
        
        # 增加了 M 键的提示
        tips = "[SPACE]: Free/Lock | [S]: Save | [M]: Move to Saved | [G]/[O]: Gripper"
        cv2.putText(canvas, tips, (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        tips2 = "Fine-tune (When Locked) -> J1~J6 Add: 1,2,3,4,5,6 | Sub: Q,W,E,R,T,Y"
        cv2.putText(canvas, tips2, (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        
        for btn in BUTTONS:
            idx = btn["idx"]
            bx, by, bw, bh = btn["rect"]
            cat, point, desc = TASKS[idx]
            
            # 判断是否已有有效数据 (不能全是0)
            task_key = f"{cat}_{point}"
            has_data = task_key in results and sum(results[task_key]) != 0
            
            if idx == current_task_idx:
                bg_color = (255, 150, 50)  # 选中态 BGR
                text_color = (255, 255, 255)
            elif has_data:
                bg_color = (50, 150, 50)   # 已保存数据
                text_color = (200, 200, 200)
            else:
                bg_color = (70, 70, 70)    # 未保存数据
                text_color = (200, 200, 200)
                
            cv2.rectangle(canvas, (bx, by), (bx + bw, by + bh), bg_color, -1)
            cv2.rectangle(canvas, (bx, by), (bx + bw, by + bh), (150, 150, 150), 1)
            cv2.putText(canvas, desc, (bx + 10, by + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, text_color, 1)

        cv2.imshow("Pro Calibration Teach Pendant", canvas)
        
        # --- 按键处理 ---
        key = cv2.waitKey(50) & 0xFF
        if key == 27:  # ESC
            break
        elif key == ord(' '):  # SPACE 切换锁定
            toggle_motors()
        elif key == ord('g') or key == ord('G'):  
            control_gripper(1)
        elif key == ord('o') or key == ord('O'):  
            control_gripper(0)
            
        # 🔥 新增：M 键 (Move) - 自动移动到已保存的点位
        elif key == ord('m') or key == ord('M'):
            cat, point, desc = TASKS[current_task_idx]
            task_key = f"{cat}_{point}"
            if task_key in results and sum(results[task_key]) != 0:
                print(f"\n🚀 自动移动至 【{desc}】: {results[task_key]}")
                locked_angles = results[task_key][:]
                mc.send_angles(locked_angles, 50)
                is_released = False # 强制切换到锁定状态，防止跌落并方便微调
            else:
                print(f"\n⚠️ 【{desc}】 尚未配置有效数据，无法自动前往！")
                
        elif key == ord('s') or key == ord('S'):  
            if is_released:
                print("\n⚠️ 请先按空格【锁定】电机，再按 S 保存！")
            else:
                cat, point, desc = TASKS[current_task_idx]
                results[f"{cat}_{point}"] = locked_angles[:]
                print(f"\n✅ 成功保存 【{desc}】: {locked_angles}")
                
        elif key == ord('1'): adjust_joint(0, 0.5)
        elif key == ord('q'): adjust_joint(0, -0.5)
        elif key == ord('2'): adjust_joint(1, 0.5)
        elif key == ord('w'): adjust_joint(1, -0.5)
        elif key == ord('3'): adjust_joint(2, 0.5)
        elif key == ord('e'): adjust_joint(2, -0.5)
        elif key == ord('4'): adjust_joint(3, 0.5)
        elif key == ord('r'): adjust_joint(3, -0.5)
        elif key == ord('5'): adjust_joint(4, 0.5)
        elif key == ord('t'): adjust_joint(4, -0.5)
        elif key == ord('6'): adjust_joint(5, 0.5)
        elif key == ord('y'): adjust_joint(5, -0.5)

except KeyboardInterrupt:
    pass
finally:
    mc.power_off()
    cv2.destroyAllWindows()
    
    # 生成代码时，包含了预加载的老数据和本次修改的新数据
    print("\n\n" + "="*60)
    print("✨ 请直接将以下代码复制并替换 config/settings.py 中的对应部分 ✨")
    print("="*60 + "\n")
    
    print("PICK_POSES = {")
    if "PICK_observe" in results: print(f'    "observe":  {results.get("PICK_observe")},')
    if "PICK_mid" in results:     print(f'    "mid":      {results.get("PICK_mid")},')
    if "PICK_grab" in results:    print(f'    "grab":     {results.get("PICK_grab")}')
    print("}\n")
    
    print("STORAGE_RACKS = {")
    for i in range(1, 7):
        print(f"    {i}: {{")
        high = results.get(f"SLOT_{i}_high", [0,0,0,0,0,0])
        mid  = results.get(f"SLOT_{i}_mid",  [0,0,0,0,0,0])
        low  = results.get(f"SLOT_{i}_low",  [0,0,0,0,0,0])
        print(f'        "high": {high},')
        print(f'        "mid":  {mid},')
        print(f'        "low":  {low}')
        print("    }," if i < 6 else "    }")
    print("}")
    print("\n" + "="*60)