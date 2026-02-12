# -*- coding: utf-8 -*-
# Copyright (c) 2026 Hangzhou Zhicheng Technology Co., Ltd. All rights reserved.
# 
# This code is proprietary and confidential.
# Unauthorized copying of this file, via any medium is strictly prohibited.
# 
# System: Coffee Intelligent Sorting System
# Author: Hangzhou Zhicheng Technology Co., Ltd
# modules/web_server.py
import os
from flask import Flask, render_template, Response, request, jsonify, stream_with_context
import cv2
import threading
import json
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
template_dir = os.path.join(root_dir, 'web', 'templates')
static_dir = os.path.join(root_dir, 'web', 'static')
config_path = os.path.join(root_dir, 'config', 'ai_config.json')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

system_state = None
ai_module = None
camera_frame = None

def get_frame():
    global camera_frame
    while True:
        if camera_frame is not None:
            ret, buffer = cv2.imencode('.jpg', camera_frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            frame = buffer.tobytes()
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.05)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(get_frame(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    if system_state: system_state.last_heartbeat = time.time()
    return jsonify("ok")

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'GET':
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        except: return jsonify({})
    else:
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(request.json, f, indent=4, ensure_ascii=False)
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "msg": str(e)}), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    log_path = os.path.join(root_dir, 'logs', 'system.log')
    if not os.path.exists(log_path):
        return jsonify({"logs": []})
    
    try:
        # 读取最后 100 行
        with open(log_path, 'r', encoding='utf-8') as f:
            # 简单粗暴的方法：读取所有行取最后100行
            # 对于2MB的文件，这完全没有性能问题
            lines = f.readlines()
            last_lines = lines[-100:] 
            
        # 清洗数据：去掉换行符
        clean_logs = [line.strip() for line in last_lines]
        return jsonify({"logs": clean_logs})
    except Exception as e:
        return jsonify({"logs": [f"Error reading logs: {str(e)}"]})

# 🔥 核心修改：流式聊天接口
@app.route('/chat', methods=['POST'])
def chat():
    # 1. 检查状态
    if system_state and system_state.mode == "AUTO":
        return Response("⛔ 自动流水线运行中，AI 已锁定。", mimetype='text/plain')

    data = request.json
    user_text = data.get('message', '')
    if not user_text: return Response("请输入指令", mimetype='text/plain')

    # 2. 定义生成器函数
    def generate():
        full_response_buffer = ""
        
        # 1. 获取当前库存作为上下文
        current_inventory = system_state.inventory if system_state else None
        
        if ai_module:
            # 获取 AI 的流式生成器
            stream = ai_module.process_text_stream(user_text, inventory=current_inventory)
            
            # 🔥 核心修复：一边收，一边发！
            for chunk in stream:
                full_response_buffer += chunk # 后台偷偷记下来
                yield chunk                   # 立刻发给前端 (实现打字机效果)
                
            # 2. 流结束后，后台提取指令 (用户看不见这步)
            if system_state:
                import re
                
                # 🔥 核心修改 1：正则同时支持 {...} 和 [...]
                # (\[|\{) 匹配 [ 或 { 开头
                # .*? 非贪婪匹配
                # (\]|\}) 匹配 ] 或 } 结尾
                json_match = re.search(r'```json\s*((\[|\{).*?(\]|\}))\s*```', full_response_buffer, re.DOTALL)
                
                if json_match:
                    try:
                        json_str = json_match.group(1)
                        cmd_data = json.loads(json_str)
                        
                        # 🔥 核心修改 2：统一标准化为 List
                        if isinstance(cmd_data, dict):
                            # 如果 AI 只发了一条指令，把它包成列表 [cmd]
                            system_state.pending_ai_cmd = [cmd_data]
                        elif isinstance(cmd_data, list):
                            # 如果 AI 发了数组，直接赋值
                            system_state.pending_ai_cmd = cmd_data
                            
                        print(f"⚡ [Web] 识别到指令: {system_state.pending_ai_cmd}")
                    except Exception as e:
                        print(f"❌ JSON Parse Error: {e}")
        else:
            yield "❌ AI 模块未连接"

    # 返回流式响应
    return Response(stream_with_context(generate()), mimetype='text/plain')
    

@app.route('/command', methods=['POST'])
def command():
    if not system_state: return jsonify({"status": "error"})
    action = request.json.get('action')
    print(f"🔘 [Web] 按钮点击: {action}")
    
    if action == 'start':
        system_state.pending_ai_cmd = {"type": "sys", "action": "start"}
    elif action == 'stop':
        system_state.pending_ai_cmd = {"type": "sys", "action": "stop"}
    elif action == 'scan':
        system_state.pending_ai_cmd = {"type": "sys", "action": "scan"}
    elif action == 'reset':
        system_state.pending_ai_cmd = {"type": "sys", "action": "reset"}
    elif action == 'clear_all': 
        system_state.pending_ai_cmd = {"type": "sys", "action": "clear_all"}

    return jsonify({"status": "ok"})

@app.route('/status')
def status():
    if not system_state: return jsonify({"inventory": {}, "mode": "OFFLINE"})
    
    msg = system_state.system_msg
    if msg:
        system_state.system_msg = None 

    return jsonify({
        "inventory": system_state.inventory,
        "mode": system_state.mode,
        "system_msg": msg
    })

def start_flask(state_obj, ai_obj):
    global system_state, ai_module
    system_state = state_obj
    ai_module = ai_obj
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def update_frame(frame):
    global camera_frame
    camera_frame = frame