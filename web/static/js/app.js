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
    console.log("系统就绪");
    initInventoryGrid();
    settingsModal = new bootstrap.Modal(document.getElementById('settingsModal'));
    setInterval(fetchStatus, 1000);
    setInterval(sendHeartbeat, 1000);
    refreshModelDisplay();
});

// 🔥 辅助函数：打字机效果
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

// 🔥 修复 1: 点击逻辑也要包含 EXECUTING
function toggleSystemMode() {
    // 如果是 自动模式 或 正在执行自动任务，点击意味着停止
    if (currentMode === 'AUTO' || currentMode === 'EXECUTING') {
        sendCommand('stop');
    } 
    // 如果是 单次任务，点击也是停止/复位
    else if (currentMode === 'SINGLE_TASK') {
        sendCommand('stop'); 
    } 
    else {
        sendCommand('start');
    }
}

// 🔥 修复 2: UI 状态映射
function updateUIState(mode) {
    currentMode = mode; 
    const btnMain = document.getElementById('btn-main-toggle');
    const statusText = document.getElementById('status-text');
    const aiBadge = document.getElementById('ai-status-badge');
    const chatInput = document.getElementById('user-input');
    const chatBtn = document.getElementById('btn-send');
    const chatBox = document.getElementById('chat-box');

    // --- 状态 A: 自动流水线 (包含 AUTO 和 EXECUTING) ---
    // 只要是这两者之一，都视为"自动模式运行中"
    if (mode === 'AUTO' || mode === 'EXECUTING') {
        btnMain.className = "btn btn-danger btn-lg w-100 mb-3 py-3 fw-bold shadow-sm";
        btnMain.innerHTML = '<i class="fas fa-stop-circle me-2"></i> 停止自动运行 (启用 AI)';
        statusText.innerHTML = '<span class="text-danger"><i class="fas fa-cog fa-spin me-1"></i> 自动流水线运行中...</span>';
        
        chatInput.disabled = true;
        chatInput.placeholder = "⛔ 自动模式运行中 (AI 已锁定)";
        chatBtn.disabled = true;
        chatBox.style.opacity = "0.6";
        chatBox.style.pointerEvents = "none";
        
        aiBadge.className = "badge bg-secondary";
        aiBadge.innerHTML = '<i class="fas fa-lock me-1"></i>AI 已锁定';
    } 
    // --- 状态 B: 单次任务中 ---
    else if (mode === 'SINGLE_TASK') {
        btnMain.className = "btn btn-warning btn-lg w-100 mb-3 py-3 fw-bold shadow-sm text-dark";
        btnMain.innerHTML = '<i class="fas fa-hourglass-half me-2"></i> 任务执行中...';
        statusText.innerHTML = '<span class="text-warning"><i class="fas fa-robot me-1"></i> AI 正在执行单次指令...</span>';
        
        chatInput.disabled = true;
        chatInput.placeholder = "⏳ 等待当前动作完成...";
        chatBtn.disabled = true;
        chatBox.style.opacity = "0.9"; 
        
        aiBadge.className = "badge bg-success";
        aiBadge.innerHTML = '<i class="fas fa-check-circle me-1"></i>AI 执行中';
    }
    // --- 状态 C: 空闲 ---
    else {
        btnMain.className = "btn btn-success btn-lg w-100 mb-3 py-3 fw-bold shadow-sm";
        btnMain.innerHTML = '<i class="fas fa-rocket me-2"></i> 启动自动分拣 (禁用 AI)';
        statusText.innerHTML = '<span class="text-success"><i class="fas fa-check-circle me-1"></i> AI 在线，可对话控制。</span>';
        
        chatInput.disabled = false;
        chatInput.placeholder = "在此输入指令 (例如：把红色的放1号)...";
        chatBtn.disabled = false;
        chatBox.style.opacity = "1.0";
        chatBox.style.pointerEvents = "auto";
        
        aiBadge.className = "badge bg-success";
        aiBadge.innerHTML = '<i class="fas fa-check-circle me-1"></i>AI 在线';
    }
}

function fetchStatus() {
    fetch('/status')
        .then(res => res.json())
        .then(data => {
            if(data.mode === "OFFLINE") return;
            
            updateInventory(data.inventory);
            
            // 处理系统消息追加 + 打字机效果
            if (data.system_msg) {
                if (activeAiBubble) {
                    const loader = activeAiBubble.querySelector('.typing-indicator');
                    if (loader) loader.remove();

                    const span = document.createElement('span');
                    if (data.system_msg.includes('⚠️') || data.system_msg.includes('❌') || data.system_msg.includes('拒绝')) {
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

            const badge = document.getElementById('sys-mode');
            // 右上角的 Badge 也要同步处理
            if (data.mode === 'AUTO' || data.mode === 'EXECUTING') {
                badge.innerText = "自动运行";
                badge.className = "badge bg-success";
            } else if (data.mode === 'SINGLE_TASK') {
                badge.innerText = "单次任务";
                badge.className = "badge bg-primary";
            } else {
                badge.innerText = "系统空闲";
                badge.className = "badge bg-warning text-dark";
            }
            
            updateUIState(data.mode);
        }).catch(err => {});
}

function sendChat() {
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

    fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    }).then(res => res.json()).then(data => {
        const bubble = appendChat("AI", data.reply, "ai", true); 
        activeAiBubble = bubble;
    });
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
function handleEnter(e) { if (e.key === 'Enter') sendChat(); }
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