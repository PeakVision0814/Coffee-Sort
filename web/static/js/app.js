let settingsModal;
let currentMode = "IDLE"; 

// 🔥 新增：用于记录当前正在等待后续系统消息的 AI 气泡 DOM 元素
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

function refreshModelDisplay() {
    fetch('/api/settings').then(res => res.json()).then(data => {
        document.getElementById('current-model-display').innerText = data.model_name || '未配置';
    }).catch(err => {});
}

function toggleSystemMode() {
    if (currentMode === 'AUTO' || currentMode === 'SINGLE_TASK') {
        sendCommand('stop');
    } else {
        sendCommand('start');
    }
}

function updateUIState(mode) {
    currentMode = mode; 
    const btnMain = document.getElementById('btn-main-toggle');
    const statusText = document.getElementById('status-text');
    const aiBadge = document.getElementById('ai-status-badge');
    const chatInput = document.getElementById('user-input');
    const chatBtn = document.getElementById('btn-send');
    const chatBox = document.getElementById('chat-box');

    if (mode === 'AUTO') {
        btnMain.className = "btn btn-danger btn-lg w-100 mb-3 py-3 fw-bold shadow-sm";
        btnMain.innerHTML = '<i class="fas fa-stop-circle me-2"></i> 停止自动运行 (启用 AI)';
        statusText.innerHTML = '<span class="text-danger"><i class="fas fa-cog fa-spin me-1"></i> 自动流水线运行中...</span>';
        chatInput.disabled = true;
        chatInput.placeholder = "⛔ 自动模式运行中 (AI 已锁定)";
        chatBtn.disabled = true;
        chatBox.style.opacity = "0.5";
        chatBox.style.pointerEvents = "none";
        aiBadge.className = "badge bg-secondary";
        aiBadge.innerHTML = '<i class="fas fa-lock me-1"></i>AI 已锁定';
    } 
    else if (mode === 'SINGLE_TASK') {
        btnMain.className = "btn btn-warning btn-lg w-100 mb-3 py-3 fw-bold shadow-sm text-dark";
        btnMain.innerHTML = '<i class="fas fa-hourglass-half me-2"></i> 任务执行中...';
        statusText.innerHTML = '<span class="text-warning"><i class="fas fa-robot me-1"></i> AI 正在执行单次指令...</span>';
        chatInput.disabled = true;
        chatInput.placeholder = "⏳ 等待当前动作完成...";
        chatBtn.disabled = true;
        chatBox.style.opacity = "0.8"; 
        aiBadge.className = "badge bg-success";
        aiBadge.innerHTML = '<i class="fas fa-check-circle me-1"></i>AI 执行中';
    }
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
            
            // 🔥 核心修改：处理系统消息的合并逻辑
            if (data.system_msg) {
                if (activeAiBubble) {
                    // 1. 如果有活跃的 AI 气泡，移除等待动画
                    const loader = activeAiBubble.querySelector('.typing-indicator');
                    if (loader) loader.remove();

                    // 2. 追加系统消息（带分隔线）
                    const sysDiv = document.createElement('div');
                    sysDiv.className = "system-append-msg";
                    sysDiv.innerHTML = data.system_msg;
                    activeAiBubble.appendChild(sysDiv);
                    
                    // 3. 滚动到底部并重置活跃气泡
                    const box = document.getElementById('chat-box');
                    box.scrollTop = box.scrollHeight;
                    activeAiBubble = null; 
                } else {
                    // 兜底：如果没有活跃气泡，还是作为单独的一条发出
                    appendChat("AI", data.system_msg, "ai");
                }
            }

            const badge = document.getElementById('sys-mode');
            if (data.mode === 'AUTO') {
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

    // 用户发送消息时，把上一个活跃气泡关掉（防止错位）
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
        // AI 回复时，带上等待动画
        const bubble = appendChat("AI", data.reply, "ai", true); // true 表示显示等待动画
        
        // 如果 AI 确实下发了指令，我们才等待系统消息
        // 如果 AI 只是闲聊（没有 command），就不要保留 activeAiBubble
        // 但这里前端不知道有没有 command，所以我们默认 AI 回复都可能是操作的前奏
        // 优化：如果 data.reply 里包含 "无法" "拒绝" 等词，可能就没有后续了？
        // 稳妥起见，我们总是标记它为活跃气泡，如果后续没有 system_msg，它就一直停在加载动画？
        // 不，我们改一下：AI 只有下发了任务才会有后续。
        // 但为了简单，我们让它显示动画。如果 3 秒内没收到系统消息，可以自动移除动画（可选优化）。
        
        activeAiBubble = bubble;
    });
}

// 🔥 修改：增加 showLoading 参数
function appendChat(sender, text, type, showLoading=false) {
    const box = document.getElementById('chat-box');
    const div = document.createElement('div');
    div.className = `chat-message msg ${type}`;
    
    let content = type === 'system' ? text : `<strong>${sender}:</strong> ${text}`;
    
    // 添加动画 HTML
    if (showLoading) {
        content += `
        <div class="typing-indicator">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>`;
    }
    
    div.innerHTML = content;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
    return div; // 返回 DOM 元素以便后续操作
}

// ... (其他函数保持不变) ...
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