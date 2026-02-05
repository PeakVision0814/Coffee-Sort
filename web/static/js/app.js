let settingsModal;
// 当前系统模式缓存
let currentMode = "IDLE"; 

const PROVIDER_DEFAULTS = {
    'deepseek': { url: 'https://api.deepseek.com', model: 'deepseek-chat' },
    'openai':   { url: 'https://api.openai.com/v1', model: 'gpt-3.5-turbo' },
    'gemini':   { url: 'https://generativelanguage.googleapis.com', model: 'gemini-pro' },
    'ollama':   { url: 'http://localhost:11434/v1', model: 'llama2' },
    'other':    { url: '', model: '' }
};

document.addEventListener('DOMContentLoaded', function() {
    console.log("System Ready.");
    initInventoryGrid();
    settingsModal = new bootstrap.Modal(document.getElementById('settingsModal'));
    setInterval(fetchStatus, 1000);
    setInterval(sendHeartbeat, 1000);
});

// 🔥 核心逻辑：单一按钮切换模式
function toggleSystemMode() {
    // 如果当前是自动或执行中，点按钮意味着“暂停/停止”
    if (currentMode === 'AUTO' || currentMode === 'EXECUTING') {
        sendCommand('stop');
    } else {
        // 否则意味着“启动”
        sendCommand('start');
    }
}

// 🔥 核心：根据模式更新 UI (互斥逻辑)
function updateUIState(mode) {
    currentMode = mode; // 更新全局缓存
    
    // 获取 DOM 元素
    const btnMain = document.getElementById('btn-main-toggle');
    const statusText = document.getElementById('status-text');
    
    // 聊天框相关元素
    const chatInput = document.getElementById('user-input');
    const chatBtn = document.querySelector('#chat-box + .card-footer button'); // 发送按钮
    const chatBox = document.getElementById('chat-box');
    
    // --- 情况 A: 正在自动分拣 (AUTO 或 EXECUTING) ---
    // 此时：按钮变红(用于停止)，AI 被锁死
    if (mode === 'AUTO' || mode === 'EXECUTING') {
        
        // 1. 按钮变形：变成 "停止" 按钮
        btnMain.className = "btn btn-danger btn-lg w-100 mb-3 py-3 fw-bold shadow-sm";
        btnMain.innerHTML = '<i class="fas fa-stop-circle me-2"></i> 停止自动运行 (进入 AI 控制)';
        
        // 2. 状态文字
        statusText.innerHTML = '<span class="text-danger"><i class="fas fa-cog fa-spin me-1"></i> 自动流水线运行中...</span>';
        
        // 3. 锁死聊天框 (视觉变灰 + 禁止输入)
        chatInput.disabled = true;
        chatInput.placeholder = "⛔ 自动模式运行中 (AI 已锁定)";
        chatBtn.disabled = true;
        
        // 让聊天记录区变灰，视觉上暗示不可用
        chatBox.style.opacity = "0.5";
        chatBox.style.filter = "grayscale(100%)";
        chatBox.style.pointerEvents = "none"; // 禁止点击
    } 
    
    // --- 情况 B: 空闲状态 (IDLE) ---
    // 此时：按钮变绿(用于启动)，AI 恢复可用
    else {
        
        // 1. 按钮变形：变成 "启动" 按钮
        btnMain.className = "btn btn-success btn-lg w-100 mb-3 py-3 fw-bold shadow-sm";
        btnMain.innerHTML = '<i class="fas fa-rocket me-2"></i> 启动自动分拣 (Disable AI)';
        
        // 2. 状态文字
        statusText.innerHTML = '<span class="text-success"><i class="fas fa-check-circle me-1"></i> AI 在线，可对话控制。</span>';

        // 3. 解锁聊天框
        chatInput.disabled = false;
        chatInput.placeholder = "在此输入指令 (例如：把红色的放1号)...";
        chatBtn.disabled = false;
        
        // 恢复视觉
        chatBox.style.opacity = "1.0";
        chatBox.style.filter = "none";
        chatBox.style.pointerEvents = "auto";
    }
}

// 轮询状态
function fetchStatus() {
    fetch('/status')
        .then(res => res.json())
        .then(data => {
            if(data.mode === "OFFLINE") return;
            
            updateInventory(data.inventory);
            
            const badge = document.getElementById('sys-mode');
            badge.innerText = data.mode;
            
            // 根据状态刷新所有 UI
            updateUIState(data.mode);

            // 顶部 Badge 颜色
            if (data.mode === 'AUTO' || data.mode === 'EXECUTING') {
                badge.className = "badge bg-success";
            } else if (data.mode === 'AI_WAIT') {
                badge.className = "badge bg-info text-dark";
            } else {
                badge.className = "badge bg-warning text-dark";
            }
        }).catch(err => {});
}

// --- 下面是常规函数，保持不变 ---

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
        document.getElementById('url-hint').innerText = provider === 'other' ? "自定义地址" : `已载入 ${provider}`;
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
            alert("✅ 保存成功");
            settingsModal.hide();
        } else alert("❌ 保存失败");
    });
}

function sendHeartbeat() { fetch('/heartbeat', { method: 'POST' }).catch(e => {}); }

function initInventoryGrid() {
    const container = document.getElementById('inventory-grid');
    container.innerHTML = '';
    for (let i = 1; i <= 6; i++) {
        container.innerHTML += `
            <div class="col-4">
                <div class="slot-box slot-free" id="slot-${i}">
                    <span class="slot-number">#${i}</span>
                    <span class="slot-status">FREE</span>
                </div>
            </div>`;
    }
}

function updateInventory(inventory) {
    for (let i = 1; i <= 6; i++) {
        const el = document.getElementById(`slot-${i}`);
        const isFull = inventory[i] === 1;
        el.className = isFull ? 'slot-box slot-full' : 'slot-box slot-free';
        el.querySelector('.slot-status').innerText = isFull ? 'FULL' : 'FREE';
    }
}

function sendCommand(action) {
    fetch('/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action })
    }).then(res => res.json())
      .then(data => {
          appendChat("System", `Command Sent: ${action.toUpperCase()}`, "system");
      });
}

function sendChat() {
    const input = document.getElementById('user-input');
    const text = input.value.trim();
    if (!text) return;
    appendChat("You", text, "user");
    input.value = '';
    fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    }).then(res => res.json()).then(data => {
        appendChat("AI", data.reply, "ai");
    });
}

function appendChat(sender, text, type) {
    const box = document.getElementById('chat-box');
    const div = document.createElement('div');
    div.className = `chat-message msg ${type}`;
    div.innerHTML = type === 'system' ? text : `<strong>${sender}:</strong> ${text}`;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function handleEnter(e) { if (e.key === 'Enter') sendChat(); }