// ... (保留前面的变量定义和 PROVIDER_DEFAULTS) ...

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
    initInventoryGrid(); // 初始化空网格
    settingsModal = new bootstrap.Modal(document.getElementById('settingsModal'));
    setInterval(fetchStatus, 1000);
    setInterval(sendHeartbeat, 1000);
    refreshModelDisplay();
});

// ... (typeWriter, refreshModelDisplay, toggleSystemMode, isSystemBusy 保持不变) ...

// 打字机动画 (保持不变)
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

// updateUIState 里的逻辑稍微适配一下 Dark Mode 的按钮颜色
function updateUIState(mode) {
    currentMode = mode; 
    const btnMain = document.getElementById('btn-main-toggle');
    const statusText = document.getElementById('status-text');
    const aiBadge = document.getElementById('ai-status-badge');
    const chatInput = document.getElementById('user-input');
    const chatBtn = document.getElementById('btn-send');
    const chatBox = document.getElementById('chat-box');

    // 解锁输入框
    chatInput.disabled = false;
    chatBox.style.pointerEvents = "auto";
    chatBtn.disabled = false;

    if (isSystemBusy()) {
        // 忙碌状态 (红色主题)
        btnMain.className = "btn btn-danger btn-lg w-100 mb-3 py-3 fw-bold shadow-lg";
        btnMain.innerHTML = '<i class="fas fa-stop-circle me-2 animate-pulse"></i> 停止运行 (STOP)';
        statusText.innerHTML = '<span class="text-danger"><i class="fas fa-cog fa-spin me-1"></i> SYSTEM BUSY</span>';
        
        aiBadge.className = "badge bg-secondary border border-secondary text-light opacity-50";
        aiBadge.innerHTML = '<i class="fas fa-lock me-1"></i>AI LOCKED';
        
        chatInput.placeholder = "⚠ 系统执行中，AI 暂时锁定...";
        chatBtn.className = "btn btn-danger fw-bold";
        chatBtn.innerHTML = '<i class="fas fa-hand-paper me-1"></i> 中断';
    } else {
        // 空闲状态 (绿色主题)
        btnMain.className = "btn btn-success btn-lg w-100 mb-3 py-3 fw-bold shadow-lg";
        btnMain.innerHTML = '<i class="fas fa-rocket me-2"></i> 启动自动分拣 (AUTO)';
        statusText.innerHTML = '<span class="text-success"><i class="fas fa-check-circle me-1"></i> SYSTEM READY</span>';
        
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
            
            // 处理系统消息 (保持你原有的逻辑)
            if (data.system_msg) {
                if (activeAiBubble) {
                    const loader = activeAiBubble.querySelector('.typing-indicator');
                    if (loader) loader.remove();
                    const span = document.createElement('span');
                    if (data.system_msg.includes('⚠️') || data.system_msg.includes('❌')) {
                        span.className = "system-append-span error";
                    } else {
                        span.className = "system-append-span";
                    }
                    span.innerHTML = " "; 
                    activeAiBubble.appendChild(span);
                    typeWriter(span, data.system_msg);
                    activeAiBubble = null; 
                } else {
                    const bubble = appendChat("AI", "", "ai", false); 
                    typeWriter(bubble, data.system_msg);
                }
            }

            // 更新 Badge (右上角连接状态)
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

// ... (sendChat, appendChat, handleEnter 保持不变) ...
async function sendChat() {
    if (isSystemBusy()) {
        sendCommand('stop');
        return;
    }

    const input = document.getElementById('user-input');
    const text = input.value.trim();
    if (!text) return;

    // 清理之前的 loading
    if (activeAiBubble) {
        const loader = activeAiBubble.querySelector('.typing-indicator');
        if (loader) loader.remove();
        activeAiBubble = null;
    }

    // 1. 显示用户消息
    appendChat("我", text, "user");
    input.value = '';

    // 2. 创建一个空的 AI 气泡
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
            
            // 自动滚动到底部
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

// 🔥 核心修改：库存可视化渲染 (图标化)
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

// 🔥 核心修改 2：新增日志处理
function appendLog(msg, type='info') {
    const terminal = document.getElementById('log-terminal');
    if (!terminal) return;

    const div = document.createElement('div');
    div.className = 'log-line';
    
    // 🔥 修改点：增加日期显示 (格式: YYYY-MM-DD HH:MM:SS)
    const now = new Date();
    // 手动拼接以保证格式统一 (或者使用 toLocaleString 并配置 options)
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
    terminal.scrollTop = terminal.scrollHeight; // 自动滚动到底部
}

function clearLogs() {
    document.getElementById('log-terminal').innerHTML = '<div class="log-line"><span class="text-muted">[SYS]</span> Logs cleared.</div>';
}

function fetchStatus() {
    fetch('/status')
        .then(res => res.json())
        .then(data => {
            if(data.mode === "OFFLINE") return;
            
            updateInventory(data.inventory);
            
            // 🔥 核心修改 3：系统消息不再进聊天框，而是进 Log
            if (data.system_msg) {
                appendLog(data.system_msg, 'sys');
            }

            // 更新 Badge
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
function sendCommand(action) {
    fetch('/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action })
    }).then(res => res.json()).then(data => {});
}
// 设置相关函数保持不变
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


// ==========================================
// 🎤 语音识别 (适配新 UI 逻辑)
// ==========================================

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
        
        // 🔥 动画逻辑：添加 mic-active 类触发 Ripple 动画
        if(btn) {
            btn.classList.add('mic-active'); // 使用 CSS 定义的动画类
            btn.classList.remove('btn-outline-secondary');
        }
        if(status) status.innerText = "🎤 正在聆听... (Listening)";
    };

    recognition.onend = function() {
        isRecording = false;
        const btn = document.getElementById('btn-mic');
        const status = document.getElementById('voice-status');
        
        // 🔥 动画逻辑：移除
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

    // onresult 和 onerror 保持不变...
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

document.addEventListener('DOMContentLoaded', function() {
    initInventoryGrid();
    settingsModal = new bootstrap.Modal(document.getElementById('settingsModal'));
    
    loadHistoryLogs(); // 🔥 新增：加载历史日志
    
    setInterval(fetchStatus, 1000);
    setInterval(sendHeartbeat, 1000);
    refreshModelDisplay();
    initSpeech();
});

// 🔥 新增：加载历史日志函数
function loadHistoryLogs() {
    fetch('/api/logs')
        .then(res => res.json())
        .then(data => {
            const terminal = document.getElementById('log-terminal');
            if (!terminal || !data.logs) return;

            // 清空初始的 [INIT] 消息 (可选)
            terminal.innerHTML = ''; 

            data.logs.forEach(line => {
                const div = document.createElement('div');
                div.className = 'log-line';
                
                // 简单的颜色高亮解析
                if (line.includes('WARN')) div.className += ' log-warn';
                else if (line.includes('ERROR')) div.className += ' log-err';
                else if (line.includes('[System]')) div.className += ' log-sys';
                else div.className += ' text-light'; // 默认白色/浅灰

                div.innerText = line; // 使用 innerText 防止 XSS，且日志本身是纯文本
                terminal.appendChild(div);
            });
            
            // 插入一条分割线，区分历史和当前
            const sep = document.createElement('div');
            sep.className = 'log-line text-muted text-center my-2';
            sep.innerText = '--- History Loaded ---';
            terminal.appendChild(sep);

            terminal.scrollTop = terminal.scrollHeight;
        })
        .catch(err => console.error("无法加载历史日志", err));
}