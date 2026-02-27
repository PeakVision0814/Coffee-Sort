# ☕ Coffee Sort - 智能机械臂分拣系统 (Smart Robotic Arm Sorting System)

简体中文 | [English](README.md)

> **Coffee Sort** 是一个融合了 **计算机视觉 (CV)**、**大语言模型 (LLM)**、**机器人控制** 与 **工业 PLC 自动化** 的智能化分拣平台。
> 它不仅能“听懂人话”、“看懂环境”，更具备了工业级的软硬件防呆与安全急停机制，实现了真正的 IT（信息技术）与 OT（运营技术）深度融合。

---

## ✨ 核心功能 (Key Features)

### 🧠 1. AI 语义大脑

* **自然语言交互**：集成大语言模型（支持 DeepSeek / OpenAI 等），支持模糊指令（如“把那个黄色的东西拿走”、“清空库存”）。
* **意图解析与拦截**：AI 自动提取 JSON 指令。系统具备逻辑拦截能力，当检测到不支持的颜色或目标槽位已满时，AI 会拒绝动作并语音提示用户。

### 🏭 2. 工业级安全与 PLC 联动

* **以太网库存同步**：基于 Snap7 协议通过网线直连底层 PLC，毫秒级读取 6 个槽位的真实物理库存状态。
* **G35 动态硬件急停**：由 PLC 控制的启动许可信号（带软件消抖）。机械臂在抓取/放置的高危环节实时监控，一旦信号丢失瞬间原位锁死。
* **G36 物理防撞复位**：系统禁用了危险的软件复位功能，完全交由操作员长按机台实体红钮（G36）触发。系统会自动计算最近的安全点位，执行“智能防撞寻路”安全归位。
* **一键安全休眠**：支持一键执行“回原点 -> 降落至最低重心 -> 电机断电释放”的安全停机标准操作，防止意外砸机。

### 👁️ 3. 视觉感知

* **颜色与轮廓识别**：精准识别指定颜色的物体（默认：红、黄、银）。
* **动态坐标映射**：自动将摄像头的像素坐标 $(u, v)$ 转换为机械臂的真实物理空间坐标 $(x, y, z)$。

### 🗣️ 4. 多模态指挥中心

* **语音指令**：基于浏览器原生 Web Speech API，一键开启自然语言对话，系统会自动记录操作日志与对话历史。
* **现代化 Web 控制台**：基于 Flask 构建，支持实时视频流监控、状态总览、在线修改 AI Prompt 及全局自动化启停。

---

## 🛠️ 硬件环境 (Hardware)

* **机械臂**：Elephant Robotics **myCobot 280 M5**。
* **PLC**：支持 S7 协议的工业 PLC（如西门子 S7-1200），IP 地址默认 `192.168.0.10`。
* **摄像头**：标准 USB 摄像头。
* **末端执行器**：气动吸泵 / 夹爪。
* **计算平台**：Windows / Linux / macOS。

---

## 🚀 快速开始 (Quick Start)

### 1. 环境准备

详细步骤请参阅 [📚 开发环境搭建指南](https://www.google.com/search?q=./docs/Environment%2520Setup/README.md)。

```bash
# 克隆项目
git clone https://github.com/YourUsername/coffee_sort.git
cd coffee_sort

# 建议创建虚拟环境
conda create -n coffee_sort python=3.10
conda activate coffee_sort

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置文件 (多机台适配)

为了适配多台物理机台（每台机器的串口号和标定点位不同），本项目的配置文件采用了 **模板分离** 的策略。

你需要将自带的 `config_example` 模板文件夹复制一份，并重命名为本地私有的 `config` 文件夹：

```bash
# Windows (CMD/PowerShell):
xcopy config_example config /E /I

# Linux / macOS:
cp -r config_example config
```

> ⚠️ **注意**：`config/` 文件夹已被 `.gitignore` 忽略，用于存放你当前机台的专属物理参数与私密 API Key。

随后，打开并编辑你刚刚生成的 `config/` 目录下的文件：

1. **AI 配置 (`ai_config.json`)**：填入你的 API Key 和 Provider。
2. **硬件配置 (`settings.py`)**：修改 `PORT` 为你的机械臂串口号（如 `COM3` 或 `/dev/ttyUSB0`），并根据当前机台微调 `PICK_POSES` 点位。

### 3. 启动系统

确保机械臂已上电，PLC 网线已连通，运行：

```bash
python main.py
```

系统会自动进行初始化归位。待终端显示 `Web 控制台已启动` 后，浏览器访问 `http://127.0.0.1:5000` 即可进入指挥中心。

---

## 🎮 操作指南

* **启动自动流水线**：在 Web 界面右上角点击“启动自动分拣”，或对 AI 说“开始流水线”。在摄像头检测到物品，且 PLC 给出 G35 许可信号后，机械臂将自动抓取并寻找空槽位放置。
* **单次 AI 分拣**：对 AI 说“把红色的放到 2 号槽”。
* **异常处理与复位**：如果遇到突发情况拔除 G35 触发了物理急停，请在清理现场后，**长按机台上的红色复位按钮（G36）3 秒**，机械臂将自动绕开障碍物归位。
* **休眠断电**：下班停机前，请点击左上角的“休眠断电”按钮，机械臂将自动降落至最低重心并释放电机，此时可安全关闭主电源。

---

## 📂 项目结构

```text
coffee_sort/
├── 📂 config/                 # [本地配置] 机器专属配置 (Git已忽略)，需从 config_example 复制生成
├── 📂 config_example/         # [配置模板] 用于 Git 追踪的默认配置模板
│   ├── ai_config.json         # AI API 密钥与系统提示词
│   ├── settings.py            # 核心常量 (串口号、GPIO 引脚定义、点位坐标)
│   └── vision_config.json     # 视觉 HSV 阈值与 ROI 区域
│
├── 📂 docs/                   # [文档中心] 包含环境搭建及 myCobot 官方手册
│
├── 📂 logs/                   # [日志中心] 
│   ├── system.log             # 核心系统运行日志 (支持 Rolling)
│   └── chat_history.json      # AI 与用户的历史对话记录
│
├── 📂 modules/                # [核心架构] 后端业务逻辑模块
│   ├── ai_decision.py         # AI 决策与指令流式解析
│   ├── arm_control.py         # 机械臂控制 (含闭环防撞、G35/G36 动态急停监控)
│   ├── plc_comm.py            # Snap7 PLC 以太网通信模块
│   ├── vision.py              # OpenCV 图像处理与手眼坐标系转换
│   └── web_server.py          # Flask Web 路由与视频流服务
│
├── 📂 tools/                  # [工程工具] 调试与标定脚本集合
│   ├── calibrate_camera.py / calibrate_eye.py  # 相机畸变与手眼标定工具
│   ├── calibrate_vision.py    # 视觉 HSV 阈值滑块调试工具
│   ├── test_gpio.py           # [诊断] 底层 GPIO 引脚电平读取测试
│   ├── tool_fine_tune.py      # [标定] 机械臂 6 轴空间点位微调工具
│   └── ...                    # 其他自动化单元测试与交互脚本
│
├── 📂 web/                    # [前端界面] UI 资源
│   ├── static/css & js        # 样式与前端交互逻辑 (语音识别、DOM 更新)
│   └── templates/index.html   # 指挥中心主控面板
│
├── main.py                    # [总控程序] 系统入口与多线程调度总线
└── requirements.txt           # Python 依赖清单
```

---

## 💻 相关设置 (Git 环境)

本项目常驻测试机台设置如下：

**1号主机：ZC-Coffee-01**

```bash
git config user.name "ZC-Coffee-01"
git config user.email "coffee_sort_01@zhicheng.com"
```

**2号主机：ZC-Coffee-02** / **3号主机：ZC-Coffee-03** (配置以此类推)

---

## 🔧 常见问题 (FAQ)

**Q: 为什么机械臂抓到一半突然锁死并报错 `E-STOP`？**
A: 系统检测到 G35 启动许可信号掉线（电平变为 0）。这是物理级的急停保护。请检查 PLC 是否主动切断了信号，或杜邦线是否松动。恢复安全后，请长按 G36 按钮执行复位。

**Q: AI 提示词里为什么不能执行复位指令？**
A: 为遵循工业设备安全规范，软件界面的复位权限已被彻底移除。所有归位操作必须由操作员在现场确认安全后，通过机台物理按钮（G36）触发。

**Q: 如何正确关闭机器？**
A: 请务必先在 Web 控制台点击左上角的 `[休眠断电]` 按钮。待机械臂折叠趴下且电机释放后，再关闭总电源，切勿在半空中直接拔电。

**Q: 摄像头画面卡顿或黑屏？**
A: 请在 `main.py` 中检查 `cv2.VideoCapture(0)` 的设备号，同时确保 USB 供电充足且未被其他程序占用。

---

## 📄 许可证 (License)

Copyright (c) 2026 Hangzhou Zhicheng Technology Co., Ltd. All Rights Reserved.

本项目为 **杭州智珵科技有限公司** 专有软件。
未经书面授权，严禁复制、分发、修改或用于商业用途。详情请参阅根目录下的 `LICENSE` 文件。