document.addEventListener('DOMContentLoaded', function() {
    console.log("System Ready.");
    initInventoryGrid();
    
    // 每 1 秒获取状态
    setInterval(fetchStatus, 1000);

    // 🔥 每 1 秒发送心跳包 (保活)
    setInterval(sendHeartbeat, 1000);
});

// --- 新增：发送心跳 ---
function sendHeartbeat() {
    fetch('/heartbeat', { method: 'POST' })
        .catch(err => {
            // 如果心跳发送失败，说明后台可能挂了
            console.warn("Heartbeat failed:", err);
            document.getElementById('sys-mode').innerText = "OFFLINE";
            document.getElementById('sys-mode').className = "badge bg-danger";
        });
}
// --------------------

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

function fetchStatus() {
    fetch('/status')
        .then(response => response.json())
        .then(data => {
            if(data.mode === "OFFLINE") return;
            updateInventory(data.inventory);
            const badge = document.getElementById('sys-mode');
            badge.innerText = data.mode;
            // 根据模式变色
            if (data.mode === 'AUTO' || data.mode === 'EXECUTING') {
                badge.className = "badge bg-success";
            } else if (data.mode === 'AI_WAIT') {
                badge.className = "badge bg-info text-dark";
            } else {
                badge.className = "badge bg-warning text-dark";
            }
        })
        .catch(err => console.error("Status fetch error:", err));
}

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

function sendCommand(action) {
    fetch('/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action })
    }).then(res => res.json())
      .then(data => {
          console.log(`Command ${action}:`, data);
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
    })
    .then(res => res.json())
    .then(data => {
        appendChat("AI", data.reply, "ai");
    });
}

function appendChat(sender, text, type) {
    const box = document.getElementById('chat-box');
    const div = document.createElement('div');
    
    div.className = `chat-message msg ${type}`;
    
    if (type === 'system') {
        div.innerHTML = `${text}`;
    } else {
        div.innerHTML = `<strong>${sender}:</strong> ${text}`;
    }
    
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function handleEnter(e) {
    if (e.key === 'Enter') sendChat();
}