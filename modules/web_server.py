from flask import Flask, render_template, Response, request, jsonify
import cv2
import threading
import json
import time

# 初始化 Flask
app = Flask(__name__, template_folder="../templates")

# 全局引用 (将在 start_server 时被赋值)
system_state = None
ai_module = None
camera_frame = None

def get_frame():
    """生成视频流"""
    global camera_frame
    while True:
        if camera_frame is not None:
            # 压缩图片以提高传输速度
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

@app.route('/chat', methods=['POST'])
def chat():
    """处理 AI 对话"""
    data = request.json
    user_text = data.get('message', '')
    
    # 1. 调用 AI 模块处理
    # 注意：ai_module.process_text 现在应该返回 {reply: "...", command: {...}}
    result = ai_module.process_text(user_text)
    
    # 2. 如果有控制指令，注入到全局状态机
    if result.get('command'):
        print(f"⚡ [Web] 注入指令: {result['command']}")
        # 只有当不在自动模式时才允许插队，或者强制打断
        # 这里我们将模式切换为 AI_WAIT，并设置指令
        system_state.mode = "AI_WAIT" 
        system_state.pending_ai_cmd = result['command']
    
    return jsonify({"reply": result.get('reply', 'AI无回复')})

@app.route('/command', methods=['POST'])
def command():
    """处理快捷按钮"""
    action = request.json.get('action')
    print(f"🔘 [Web] 按钮点击: {action}")
    
    if action == 'start':
        system_state.mode = "AUTO"
    elif action == 'stop':
        system_state.mode = "IDLE"
    elif action == 'scan':
        # 这里只是置标志位，具体逻辑由 main.py 里的循环去执行
        system_state.pending_ai_cmd = {"type": "sys", "action": "scan"}
        system_state.mode = "AI_WAIT" # 切换过去以便执行特殊指令
    elif action == 'reset':
        system_state.pending_ai_cmd = {"type": "arm", "action": "go_home"}
        system_state.mode = "AI_WAIT"
        
    return jsonify({"status": "ok"})

@app.route('/status')
def status():
    """前端轮询状态"""
    return jsonify({
        "inventory": system_state.inventory,
        "mode": system_state.mode
    })

def start_flask(state_obj, ai_obj):
    """启动 Flask 服务的函数 (将在 main.py 的线程中调用)"""
    global system_state, ai_module
    system_state = state_obj
    ai_module = ai_obj
    
    # 关闭 Flask 的启动提示，让控制台清爽点
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    print(">>> 🌐 Web 控制台已启动: http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def update_frame(frame):
    """main.py 调用此函数更新视频流"""
    global camera_frame
    camera_frame = frame