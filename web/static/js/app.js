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
    setInterval(fetchStatus, 1000);
    setInterval(sendHeartbeat, 1000);
    refreshModelDisplay();
});

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

    // 解锁输入框，允许随时打字
    chatInput.disabled = false;
    chatBox.style.pointerEvents = "auto";
    chatBtn.disabled = false;

    if (isSystemBusy()) {
        // 忙碌状态
        btnMain.className = "btn btn-danger btn-lg w-100 mb-3 py-3 fw-bold shadow-sm";
        btnMain.innerHTML = '<i class="fas fa-stop-circle me-2"></i> 停止自动运行';
        statusText.innerHTML = '<span class="text-danger"><i class="fas fa-cog fa-spin me-1"></i> 系统运行中...</span>';
        
        aiBadge.className = "badge bg-secondary";
        aiBadge.innerHTML = '<i class="fas fa-lock me-1"></i>AI 锁定';
        
        chatBox.style.opacity = "0.8";
        chatInput.placeholder = "正在执行中...";
        chatBtn.className = "btn btn-danger px-4";
        chatBtn.innerHTML = '<i class="fas fa-sync-alt fa-spin me-1"></i> 停止';
    } else {
        // 空闲状态
        btnMain.className = "btn btn-success btn-lg w-100 mb-3 py-3 fw-bold shadow-sm";
        btnMain.innerHTML = '<i class="fas fa-rocket me-2"></i> 启动自动分拣';
        statusText.innerHTML = '<span class="text-success"><i class="fas fa-check-circle me-1"></i> 系统就绪</span>';
        
        aiBadge.className = "badge bg-success";
        aiBadge.innerHTML = '<i class="fas fa-check-circle me-1"></i>AI 在线';
        
        chatBox.style.opacity = "1.0";
        chatInput.placeholder = "请输入指令...";
        chatBtn.className = "btn btn-primary px-4";
        chatBtn.innerHTML = '发送 <i class="fas fa-paper-plane ms-2"></i>';
    }
}

function fetchStatus() {
    fetch('/status')
        .then(res => res.json())
        .then(data => {
            if(data.mode === "OFFLINE") return;
            
            updateInventory(data.inventory);
            
            // 🔥 核心修复区
            if (data.system_msg) {
                if (activeAiBubble) {
                    // 1. 移除动画
                    const loader = activeAiBubble.querySelector('.typing-indicator');
                    if (loader) loader.remove();

                    // 2. 创建追加的文本容器
                    const span = document.createElement('span');
                    
                    if (data.system_msg.includes('⚠️') || data.system_msg.includes('❌')) {
                        span.className = "system-append-span error";
                    } else {
                        span.className = "system-append-span";
                    }
                    
                    // 🔥 修复：这里只给一个空格，不要赋值 data.system_msg，否则会重复！
                    span.innerHTML = " "; 
                    
                    activeAiBubble.appendChild(span);
                    
                    // 3. 启动打字机 (这才是唯一一次输出文本的地方)
                    typeWriter(span, data.system_msg);
                    
                    activeAiBubble = null; 
                } else {
                    const bubble = appendChat("AI", "", "ai", false); 
                    typeWriter(bubble, data.system_msg);
                }
            }

            // 更新 Badge
            const badge = document.getElementById('sys-mode');
            if (isSystemBusy()) {
                badge.innerText = "运行中";
                badge.className = "badge bg-success";
            } else {
                badge.innerText = "空闲";
                badge.className = "badge bg-warning text-dark";
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
        
        // ❌ 这里删掉了 speakText()，只显示文字

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

// 辅助函数
function initInventoryGrid() {
    const container = document.getElementById('inventory-grid');
    container.innerHTML = '';
    for (let i = 1; i <= 6; i++) {
        container.innerHTML += `
            <div class="col-4">
                <div class="slot-box slot-free" id="slot-${i}">
                    <span class="slot-number">#${i}</span>
                    <span class="slot-status">空闲</span>
                </div>
            </div>`;
    }
}
function updateInventory(inventory) {
    for (let i = 1; i <= 6; i++) {
        const el = document.getElementById(`slot-${i}`);
        const isFull = inventory[i] === 1;
        el.className = isFull ? 'slot-box slot-full' : 'slot-box slot-free';
        el.querySelector('.slot-status').innerText = isFull ? '已满' : '空闲';
    }
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
// 🎤 仅语音识别 (Web Speech API) 
// ==========================================

let recognition = null;
let isRecording = false;

// 初始化语音识别
function initSpeech() {
    // 兼容性检查
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn("当前浏览器不支持 Web Speech API");
        const btn = document.getElementById('btn-mic');
        if(btn) btn.style.display = 'none';
        return;
    }
    
    recognition = new SpeechRecognition();
    recognition.continuous = false; // 说完一句自动停止
    recognition.interimResults = true; // 显示临时结果
    recognition.lang = 'zh-CN'; // 中文

    recognition.onstart = function() {
        isRecording = true;
        const btn = document.getElementById('btn-mic');
        if(btn) {
            btn.classList.add('btn-danger', 'text-white');
            btn.classList.remove('btn-outline-secondary');
        }
        const status = document.getElementById('voice-status');
        if(status) status.innerText = "🎤 正在聆听... (请说话)";
    };

    recognition.onend = function() {
        isRecording = false;
        const btn = document.getElementById('btn-mic');
        if(btn) {
            btn.classList.remove('btn-danger', 'text-white');
            btn.classList.add('btn-outline-secondary');
        }
        const status = document.getElementById('voice-status');
        if(status) status.innerText = "";
        
        // 语音结束后，如果输入框有内容，自动发送
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
            if (finalTranscript) {
                input.value = finalTranscript;
            } else {
                input.placeholder = interimTranscript; 
            }
        }
    };
    
    recognition.onerror = function(event) {
        console.error("语音识别错误:", event.error);
        const status = document.getElementById('voice-status');
        if(status) status.innerText = "❌ 识别错误: " + event.error;
    };
}

// 切换录音状态
function toggleSpeechRecognition() {
    if (!recognition) initSpeech();
    if (!recognition) return;

    if (isRecording) {
        recognition.stop();
    } else {
        recognition.start();
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initSpeech();
});