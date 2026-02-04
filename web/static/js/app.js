// web/static/js/app.js
// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    console.log("System Ready.");
    initInventoryGrid();
    // 启动定时轮询状态 (每1秒一次)
    setInterval(fetchStatus, 1000);
});

// 初始化 6 个槽位的 HTML
function initInventoryGrid() {
    const container = document.getElementById('inventory-grid');
    container.innerHTML = '';
    for (let i = 1; i <= 6; i++) {
        const html = `
            <div class="col-4">
                <div class="slot-box slot-free" id="slot-${i}">
                    <span class="slot-number">#${i}</span>
                    <span class="slot-status">FREE</span>
                </div>
            </div>
        `;
        container.innerHTML += html;
    }
}

// 获取后台状态
function fetchStatus() {
    fetch('/status')
        .then(response => response.json())
        .then(data => {
            updateInventory(data.inventory);
            document.getElementById('sys-mode').innerText = data.mode;
        })
        .catch(err => console.error("Status fetch error:", err));
}

// 更新库存 UI
function updateInventory(inventory) {
    for (let i = 1; i <= 6; i++) {
        const el = document.getElementById(`slot-${i}`);
        const isFull = inventory[i] === 1;
        
        if (isFull) {
            el.className = 'slot-box slot-full';
            el.querySelector('.slot-status').innerText = 'FULL';
        } else {
            el.className = 'slot-box slot-free';
            el.querySelector('.slot-status').innerText = 'FREE';
        }
    }
}

// 发送控制指令
function sendCommand(action) {
    fetch('/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action })
    }).then(res => res.json())
      .then(data => {
          console.log(`Command ${action}:`, data);
          appendChat("System", `Executing: ${action.toUpperCase()}`, "system");
      });
}

// 发送 AI 聊天
function sendChat() {
    const input = document.getElementById('user-input');
    const text = input.value.trim();
    if (!text) return;

    // 1. 显示用户的话
    appendChat("You", text, "user");
    input.value = '';

    // 2. 发给后台
    fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    })
    .then(res => res.json())
    .then(data => {
        // 3. 显示 AI 回复
        appendChat("AI", data.reply, "ai");
    });
}

// 辅助：往聊天框加文字
function appendChat(sender, text, type) {
    const box = document.getElementById('chat-box');
    const div = document.createElement('div');
    
    // 组合类名：chat-message 是基础样式，type (user/ai/system) 控制颜色和位置
    div.className = `chat-message msg ${type}`;
    
    if (type === 'system') {
        div.innerHTML = `${text}`;
    } else {
        // 给名字加个小标题
        div.innerHTML = `<strong>${sender}:</strong> ${text}`;
    }
    
    box.appendChild(div);
    box.scrollTop = box.scrollHeight; // 自动滚到底部
}

// 辅助：回车发送
function handleEnter(e) {
    if (e.key === 'Enter') sendChat();
}