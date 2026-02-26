// web/static/js/app.js

let settingsModal;
let currentMode = "IDLE"; 
let activeAiBubble = null;

const PROVIDER_DEFAULTS = {
    'deepseek': { url: 'https://api.deepseek.com', model: 'deepseek-chat' },
    'openai':   { url: 'https://api.openai.com/v1', model: 'gpt-3.5-turbo' },
    'gemini':   { url: 'https://generativelanguage.googleapis.com', model: 'gemini-pro' },
    'ollama':   { url: 'http://localhost:11434/v1', model: 'llama2' },
    'other':    { url: '', model: '' }
};

document.addEventListener('DOMContentLoaded', function() {
    initInventoryGrid(); 
    settingsModal = new bootstrap.Modal(document.getElementById('settingsModal'));
    
    loadHistoryLogs(); // 加载系统日志
    loadChatHistory(); // 🔥 新增：加载聊天历史
    
    setInterval(fetchStatus, 1000);
    setInterval(sendHeartbeat, 1000);
    refreshModelDisplay();
    initSpeech();
});

// 🔥 新增：加载聊天历史函数
function loadChatHistory() {
    fetch('/api/chat_history')
        .then(res => res.json())
        .then(data => {
            const history = data.history;
            if (!history || history.length === 0) return;

            history.forEach(item => {
                // 处理 'system' 类型消息 (操作日志)
                if (item.type === 'system') {
                    const box = document.getElementById('chat-box');
                    const row = document.createElement('div');
                    row.className = 'chat-row system';
                    // 显示简单的灰色操作记录
                    row.innerHTML = `<div class="chat-message system" style="font-size: 0.75rem; opacity: 0.8;">
                        <i class="fas fa-terminal me-1"></i> ${item.message} 
                        <span class="ms-2" style="font-size:0.7em; opacity:0.6;">${item.timestamp}</span>
                    </div>`;
                    box.appendChild(row);
                } else {
                    // 普通对话：复用 appendChat
                    appendChat(item.sender, item.message, item.type, false);
                }
            });
            
            // 插入一条历史分割线
            const box = document.getElementById('chat-box');
            const sep = document.createElement('div');
            sep.className = 'chat-row system my-3';
            sep.innerHTML = '<span class="badge bg-secondary bg-opacity-25 text-light border border-secondary" style="font-size: 0.7rem;">--- 以上是历史记录 ---</span>';
            box.appendChild(sep);
            
            box.scrollTop = box.scrollHeight;
        })
        .catch(err => console.error("加载聊天记录失败", err));
}

// 打字机动画
function typeWriter(element, text, speed = 30) {
    let i = 0;
    function type() {
        if (i < text.length) {
            element.innerHTML += text.charAt(i);
            i++;
            const box = document.getElementById('chat-box');
            box.scrollTop = box.scrollHeight;
            setTimeout(type, speed);
        }
    }
    type();
}

function refreshModelDisplay() {
    fetch('/api/settings').then(res => res.json()).then(data => {
        document.getElementById('current-model-display').innerText = data.model_name || '未配置';
    }).catch(err => {});
}

function toggleSystemMode() {
    if (isSystemBusy()) sendCommand('stop');
    else sendCommand('start');
}

function isSystemBusy() {
    return (currentMode === 'AUTO' || currentMode === 'EXECUTING' || 
            currentMode === 'SINGLE_TASK' || currentMode === 'SORTING_TASK');
}

function updateUIState(mode) {
    currentMode = mode; 
    const btnMain = document.getElementById('btn-main-toggle');
    const statusText = document.getElementById('status-text');
    const aiBadge = document.getElementById('ai-status-badge');
    const chatInput = document.getElementById('user-input');
    const chatBtn = document.getElementById('btn-send');
    const chatBox = document.getElementById('chat-box');

    chatInput.disabled = false;
    chatBox.style.pointerEvents = "auto";
    chatBtn.disabled = false;

    if (isSystemBusy()) {
        // 🔥 修改点 1：使用小巧的 btn-sm 和红色样式
        btnMain.className = "btn btn-danger btn-sm fw-bold px-3 shadow-sm";
        btnMain.innerHTML = '<i class="fas fa-stop-circle me-1 animate-pulse"></i> 停止运行';
        
        // 🔥 修改点 2：精简状态文字，适应头部狭小空间
        statusText.innerHTML = '<span class="text-danger"><i class="fas fa-cog fa-spin me-1"></i> BUSY</span>';
        
        aiBadge.className = "badge bg-secondary border border-secondary text-light opacity-50";
        aiBadge.innerHTML = '<i class="fas fa-lock me-1"></i>AI LOCKED';
        
        chatInput.placeholder = "⚠ 系统执行中，AI 暂时锁定...";
        chatBtn.className = "btn btn-danger fw-bold";
        chatBtn.innerHTML = '<i class="fas fa-hand-paper me-1"></i> 中断';
    } else {
        // 🔥 修改点 3：使用小巧的 btn-sm 和绿色样式
        btnMain.className = "btn btn-success btn-sm fw-bold px-3 shadow-sm";
        btnMain.innerHTML = '<i class="fas fa-power-off me-1"></i> 启动自动分拣';
        
        // 🔥 修改点 4：精简状态文字
        statusText.innerHTML = '<span class="text-success"><i class="fas fa-check-circle me-1"></i> READY</span>';
        
        aiBadge.className = "badge bg-success bg-opacity-25 text-success border border-success";
        aiBadge.innerHTML = '<i class="fas fa-brain me-1"></i>AI ACTIVE';
        
        chatInput.placeholder = "输入指令 (支持语音)...";
        chatBtn.className = "btn btn-info text-white fw-bold";
        chatBtn.innerHTML = '发送 <i class="fas fa-paper-plane ms-2"></i>';
    }
}

function fetchStatus() {
    fetch('/status')
        .then(res => res.json())
        .then(data => {
            if(data.mode === "OFFLINE") return;
            
            updateInventory(data.inventory);
            
            // 🔥 核心修复：系统消息必须进 Log，绝对不能进 Chat！
            // ❌ 之前的错误代码是: appendChat(...) 或 typeWriter(...)
            // ✅ 正确代码是: appendLog(...)
            if (data.system_msg) {
                appendLog(data.system_msg, 'sys');
            }

            // 更新右上角状态 Badge
            const badge = document.getElementById('sys-mode');
            if (isSystemBusy()) {
                badge.innerHTML = '<i class="fas fa-bolt text-warning me-1"></i> WORKING';
                badge.className = "badge bg-dark border border-warning text-warning";
            } else {
                badge.innerHTML = '<i class="fas fa-check text-success me-1"></i> ONLINE';
                badge.className = "badge bg-dark border border-success text-success";
            }
            
            updateUIState(data.mode);
        }).catch(err => {});
}

async function sendChat() {
    if (isSystemBusy()) {
        sendCommand('stop');
        return;
    }

    const input = document.getElementById('user-input');
    const text = input.value.trim();
    if (!text) return;

    if (activeAiBubble) {
        const loader = activeAiBubble.querySelector('.typing-indicator');
        if (loader) loader.remove();
        activeAiBubble = null;
    }

    appendChat("我", text, "user");
    input.value = '';

    const aiBubble = appendChat("AI", "", "ai", true); 
    activeAiBubble = aiBubble; 
    const loader = aiBubble.querySelector('.typing-indicator');

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let isFirstChunk = true;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            if (isFirstChunk) {
                if (loader) loader.remove();
                isFirstChunk = false;
            }

            const chunk = decoder.decode(value, { stream: true });
            aiBubble.innerHTML += chunk; 
            
            const box = document.getElementById('chat-box');
            box.scrollTop = box.scrollHeight;
        }

    } catch (err) {
        aiBubble.innerHTML += "<br>[连接断开]";
    } finally {
        activeAiBubble = null;
    }
}

function appendChat(sender, text, type, showLoading=false) {
    const box = document.getElementById('chat-box');
    const row = document.createElement('div');
    row.className = `chat-row ${type}`;

    if (type !== 'system') {
        const avatar = document.createElement('div');
        avatar.className = `avatar ${type}`;
        if (type === 'ai') {
            avatar.innerHTML = '<i class="fas fa-robot"></i>';
        } else {
            avatar.innerHTML = '<i class="fas fa-user"></i>';
        }
        row.appendChild(avatar);
    }

    const bubble = document.createElement('div');
    bubble.className = `chat-message ${type}`;
    
    let content = text;
    if (showLoading) {
        content += `
        <div class="typing-indicator">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>`;
    }
    
    bubble.innerHTML = content;
    row.appendChild(bubble);
    box.appendChild(row);
    box.scrollTop = box.scrollHeight;
    return bubble; 
}

function handleEnter(e) { 
    if (e.key === 'Enter') {
        if (isSystemBusy()) return;
        sendChat(); 
    }
}

function initInventoryGrid() {
    const container = document.getElementById('inventory-grid');
    container.innerHTML = '';
    for (let i = 1; i <= 6; i++) {
        container.innerHTML += `
            <div class="col-2">
                <div class="slot-box" id="slot-${i}" title="${i}号槽位">
                    <span class="slot-number">#${i}</span>
                    <i class="fas fa-box-open slot-icon"></i>
                </div>
            </div>`;
    }
}

function updateInventory(inventory) {
    for (let i = 1; i <= 6; i++) {
        const el = document.getElementById(`slot-${i}`);
        const icon = el.querySelector('.slot-icon');
        
        const isFull = inventory[i] === 1;
        
        if (isFull) {
            el.className = 'slot-box slot-full';
            icon.className = 'fas fa-cube slot-icon';
        } else {
            el.className = 'slot-box';
            icon.className = 'fas fa-box-open slot-icon';
        }
    }
}

function appendLog(msg, type='info') {
    const terminal = document.getElementById('log-terminal');
    if (!terminal) return;

    const div = document.createElement('div');
    div.className = 'log-line';
    
    const now = new Date();
    const dateStr = now.toLocaleDateString('zh-CN').replace(/\//g, '-');
    const timeStr = now.toLocaleTimeString('en-GB', { hour12: false });
    const fullTime = `${dateStr} ${timeStr}`;

    let colorClass = 'text-light';
    
    if (msg.includes('⚠️') || type === 'warn') colorClass = 'log-warn';
    else if (msg.includes('❌') || type === 'error') colorClass = 'log-err';
    else if (msg.includes('🤖')) colorClass = 'log-sys';
    else if (type === 'success') colorClass = 'log-info';

    div.innerHTML = `<span class="text-muted">[${fullTime}]</span> <span class="${colorClass}">${msg}</span>`;
    
    terminal.appendChild(div);
    terminal.scrollTop = terminal.scrollHeight;
}

function loadHistoryLogs() {
    fetch('/api/logs')
        .then(res => res.json())
        .then(data => {
            const terminal = document.getElementById('log-terminal');
            if (!terminal || !data.logs) return;

            terminal.innerHTML = ''; 

            data.logs.forEach(line => {
                const div = document.createElement('div');
                div.className = 'log-line';
                
                if (line.includes('WARN')) div.className += ' log-warn';
                else if (line.includes('ERROR')) div.className += ' log-err';
                else if (line.includes('[System]')) div.className += ' log-sys';
                else div.className += ' text-light';

                div.innerText = line; 
                terminal.appendChild(div);
            });
            
            const sep = document.createElement('div');
            sep.className = 'log-line text-muted text-center my-2';
            sep.innerText = '--- History Loaded ---';
            terminal.appendChild(sep);

            terminal.scrollTop = terminal.scrollHeight;
        })
        .catch(err => console.error("无法加载历史日志", err));
}

function sendCommand(action) {
    fetch('/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action })
    }).then(res => res.json()).then(data => {});
}

function openSettings() {
    fetch('/api/settings').then(res => res.json()).then(data => {
        const provider = data.provider || 'deepseek';
        document.getElementById('cfg-provider').value = provider;
        document.getElementById('cfg-api-key').value = data.api_key || '';
        document.getElementById('cfg-base-url').value = data.base_url || '';
        document.getElementById('cfg-model').value = data.model_name || '';
        document.getElementById('cfg-prompt').value = data.system_prompt || '';
        document.getElementById('cfg-api-key').type = "password";
        settingsModal.show();
    });
}
function updateBaseUrl() {
    const provider = document.getElementById('cfg-provider').value;
    const defaults = PROVIDER_DEFAULTS[provider];
    if (defaults) {
        document.getElementById('cfg-base-url').value = defaults.url;
        if (provider !== 'other') document.getElementById('cfg-model').value = defaults.model;
        document.getElementById('url-hint').innerText = provider === 'other' ? "请输入自定义地址" : `已自动载入 ${provider} 地址`;
    }
}
function toggleKeyVisibility() {
    const input = document.getElementById('cfg-api-key');
    input.type = input.type === "password" ? "text" : "password";
}
function saveSettings() {
    const newConfig = {
        provider: document.getElementById('cfg-provider').value,
        api_key: document.getElementById('cfg-api-key').value,
        base_url: document.getElementById('cfg-base-url').value,
        model_name: document.getElementById('cfg-model').value,
        system_prompt: document.getElementById('cfg-prompt').value
    };
    fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
    }).then(res => res.json()).then(data => {
        if (data.status === 'success') {
            alert("✅ 配置已保存！");
            settingsModal.hide();
            refreshModelDisplay();
        } else alert("❌ 保存失败");
    });
}
function sendHeartbeat() { fetch('/heartbeat', { method: 'POST' }).catch(e => {}); }

let recognition = null;
let isRecording = false;

function initSpeech() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn("当前浏览器不支持 Web Speech API");
        const btn = document.getElementById('btn-mic');
        if(btn) btn.style.display = 'none';
        return;
    }
    
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'zh-CN';

    recognition.onstart = function() {
        isRecording = true;
        const btn = document.getElementById('btn-mic');
        const status = document.getElementById('voice-status');
        
        if(btn) {
            btn.classList.add('mic-active');
            btn.classList.remove('btn-outline-secondary');
        }
        if(status) status.innerText = "🎤 正在聆听... (Listening)";
    };

    recognition.onend = function() {
        isRecording = false;
        const btn = document.getElementById('btn-mic');
        const status = document.getElementById('voice-status');
        
        if(btn) {
            btn.classList.remove('mic-active');
            btn.classList.add('btn-outline-secondary');
        }
        if(status) status.innerText = "";
        
        const input = document.getElementById('user-input');
        if (input && input.value.trim().length > 0) {
            sendChat(); 
        }
    };

    recognition.onresult = function(event) {
        let interimTranscript = '';
        let finalTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript;
            } else {
                interimTranscript += event.results[i][0].transcript;
            }
        }
        const input = document.getElementById('user-input');
        if (input) {
            if (finalTranscript) input.value = finalTranscript;
            else input.placeholder = interimTranscript; 
        }
    };
    
    recognition.onerror = function(event) {
        console.error("语音识别错误:", event.error);
        const status = document.getElementById('voice-status');
        if(status) status.innerText = "❌ Error: " + event.error;
    };
}

function toggleSpeechRecognition() {
    if (!recognition) initSpeech();
    if (!recognition) return;
    if (isRecording) recognition.stop();
    else recognition.start();
}