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

function sendChat() {
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
// Settings functions omitted for brevity but should be kept if needed
function openSettings() { fetch('/api/settings').then(res => res.json()).then(data => { settingsModal.show(); }); }
function saveSettings() { settingsModal.hide(); } 
function sendHeartbeat() { fetch('/heartbeat', { method: 'POST' }).catch(e => {}); }