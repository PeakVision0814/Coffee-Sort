import os
from flask import Flask, render_template, Response, request, jsonify
import cv2
import threading
import json
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
template_dir = os.path.join(root_dir, 'web', 'templates')
static_dir = os.path.join(root_dir, 'web', 'static')

app = Flask(__name__, 
            template_folder=template_dir, 
            static_folder=static_dir)

system_state = None
ai_module = None
camera_frame = None

def get_frame():
    global camera_frame
    while True:
        if camera_frame is not None:
            ret, buffer = cv2.imencode('.jpg', camera_frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.05)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(get_frame(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- 🔥 新增心跳接口 ---
@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    """前端 JS 每秒调用一次，证明浏览器还开着"""
    if system_state:
        # 更新最后心跳时间为当前时间
        system_state.last_heartbeat = time.time()
    return jsonify("ok")
# ---------------------

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_text = data.get('message', '')
    if not user_text: return jsonify({"reply": "请输入指令"})

    if ai_module:
        result = ai_module.process_text(user_text)
    else:
        result = {"reply": "AI模块未连接", "command": None}
    
    if result.get('command') and system_state:
        print(f"⚡ [Web] 注入指令: {result['command']}")
        system_state.mode = "AI_WAIT" 
        system_state.pending_ai_cmd = result['command']
    
    return jsonify({"reply": result.get('reply', 'AI无回复')})

@app.route('/command', methods=['POST'])
def command():
    if not system_state: return jsonify({"status": "error"})

    action = request.json.get('action')
    print(f"🔘 [Web] 按钮点击: {action}")
    
    if action == 'start':
        system_state.mode = "AUTO"
    elif action == 'stop':
        system_state.mode = "IDLE"
    elif action == 'scan':
        system_state.pending_ai_cmd = {"type": "sys", "action": "scan"}
        system_state.mode = "AI_WAIT" 
    elif action == 'reset':
        system_state.pending_ai_cmd = {"type": "arm", "action": "go_home"}
        system_state.mode = "AI_WAIT"
    elif action == 'clear_all': 
        system_state.inventory = {i: 0 for i in range(1, 7)}
        print("🧹 [Web] 库存已清空")

    return jsonify({"status": "ok"})

@app.route('/status')
def status():
    if not system_state: return jsonify({"inventory": {}, "mode": "OFFLINE"})
    return jsonify({
        "inventory": system_state.inventory,
        "mode": system_state.mode
    })

def start_flask(state_obj, ai_obj):
    global system_state, ai_module
    system_state = state_obj
    ai_module = ai_obj
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    print(">>> 🌐 Web 控制台已启动: http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def update_frame(frame):
    global camera_frame
    camera_frame = frame