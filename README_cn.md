# ☕ Coffee Sort - 智能机械臂分拣系统 (Smart Robotic Arm Sorting System)

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.5+-red.svg)](https://opencv.org/)
[![myCobot](https://img.shields.io/badge/Hardware-myCobot%20280-orange.svg)](https://www.elephantrobotics.com/en/mycobot-en/)

> **Coffee Sort** 是一个融合了 **计算机视觉 (CV)**、**大语言模型 (LLM)** 和 **机器人控制** 的智能化分拣平台。
> 
> 它不仅仅是一个执行脚本的机器，更是一个能“听懂人话”、能“看懂环境”并具备“安全意识”的智能助手。

---

## ✨ 核心功能 (Key Features)

### 🧠 1. AI 语义大脑
* **自然语言交互**：通过集成OpenAI API，支持模糊指令（如“把那个黄色的东西拿走”、“清空库存”）。
* **智能解析**：AI 自动从自然对话中提取 JSON 控制指令，实现“所说即所得”。

### 🗣️ 2. 多模态控制
* **语音指令**：基于浏览器原生 Web Speech API，无需唤醒词，点击麦克风即可语音控制机械臂。
* **Web 控制台**：基于 Flask 构建的现代化仪表盘，支持实时视频流监控、一键启停和参数热修改。

### 👁️ 3. 视觉感知
* **颜色识别**：精准识别 Red, Blue, Yellow物体。
* **坐标映射**：自动将摄像头的像素坐标 $(u, v)$ 转换为机械臂的空间坐标 $(x, y, z)$。
* **动态标注**：在视频流中实时绘制识别框与置信度。

### 🛡️ 4. 安全与容错
* **库存感知**：AI 决策前会检查库存状态，**拒绝**向【已满】的槽位放置物品，防止物理碰撞。
* **智能复位**：启动任务前强制执行 `power_on` (上电) 和归位动作，解决机械臂待机下垂导致的路径规划错误。

---

## 🛠️ 硬件要求 (Hardware)

* **机械臂**：Elephant Robotics **myCobot 280 M5** (Atom + Basic)。
* **摄像头**：标准 USB 摄像头 (安装于机械臂上方或侧方)。
* **末端执行器**：吸泵 (Suction Pump) 或 夹爪 (Gripper)。
* **计算平台**：Windows / Linux / macOS (需安装 Python 环境)。

---

## 🚀 快速开始 (Quick Start)

### 1. 环境准备
详细步骤请参阅 [📚 开发环境搭建指南](./docs/Environment%20Setup/README.md)。

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

### 2. 配置文件

你需要配置 API Key 和 串口号。

1. **AI 配置**：
复制示例文件并填入你的 API Key (推荐使用 DeepSeek)。
```bash
cp config/ai_config.json.example config/ai_config.json
# 编辑 config/ai_config.json 填入 api_key
```


2. **硬件配置**：
打开 `config/settings.py`，修改 `PORT` 为你的机械臂串口号（如 `COM3` 或 `/dev/ttyUSB0`）。

### 3. 启动系统

确保机械臂已连接并上电，运行：

```bash
python main.py
```

终端显示 `>>> 🌐 Web 控制台已启动` 后，浏览器会自动打开 `http://127.0.0.1:5000`。

---

## 🎮 操作指南

### 方式一：语音控制 (推荐)

1. 点击网页输入框旁的 **🎤 麦克风** 图标。
2. 允许浏览器使用麦克风。
3. 说出指令，例如：
* “启动自动分拣模式”
* “把黄色的盒子放到 3 号”
* “复位机械臂”

### 方式二：文字对话

在输入框输入自然语言，例如：“我看 2 号位满了，把它清空一下”，AI 会解析意图并执行。

### 方式三：手动控制

点击右侧面板的按钮，进行 **[启动]**、**[复位]** 或 **[清空库存]** 操作。

---

## 📂 项目结构

```text
coffee_sort/
├── 📂 config/                     # [配置中心] 存放所有硬件、AI及系统参数
│   ├── ai_config.json             # AI 配置文件 (包含 API Key, System Prompt 等敏感信息)
│   ├── ai_config.json.example     # AI 配置模板 (用于 Git 提交，不含敏感 Key)
│   ├── calibration.json           # 机械臂与摄像头的标定数据 (手眼标定结果)
│   ├── camera_matrix.npz          # 摄像头内参矩阵文件 (OpenCV 校准生成)
│   ├── settings.py                # 全局常量设置 (串口号、波特率、预设点位坐标)
│   └── vision_config.json         # 视觉参数配置 (HSV 颜色阈值、识别区域 ROI)
│
├── 📂 docs/                       # [文档中心] 开发与硬件指南
│   ├── 📂 Environment Setup/      # 环境搭建指南 (Anaconda, Git, Python)
│   ├── 📂 myCobot_280_M5/         # 机械臂官方硬件手册与 API 说明
│   └── README.md                  # 文档中心索引
│
├── 📂 modules/                    # [核心模块] 后端逻辑实现
│   ├── ai_decision.py             # AI 决策模块 (调用 LLM, 流式解析指令, 库存检查)
│   ├── arm_control.py             # 机械臂控制模块 (封装 pymycobot, 安全复位, 运动规划)
│   ├── mock_hardware.py           # 硬件模拟模块 (无实物时的仿真测试)
│   ├── plc_comm.py                # PLC 通信模块 (Modbus/IO 扩展控制)
│   ├── vision.py                  # 视觉感知模块 (OpenCV 图像处理, 坐标转换)
│   ├── web_server.py              # Web 服务端 (Flask, Socket, 视频流推送)
│   └── README.md                  # 模块功能详细说明
│
├── 📂 scripts/                    # [工具脚本] 调试、标定与测试工具
│   ├── calibrate_camera.py        # 摄像头畸变校准脚本
│   ├── calibrate_eye.py           # 手眼标定脚本 (计算相机与机械臂的坐标关系)
│   ├── calibrate_vision.py        # 视觉阈值调试工具 (实时滑块调节 HSV)
│   ├── debug_auto_test.py         # 自动化流程测试脚本
│   ├── debug_interactive.py       # 交互式调试脚本
│   ├── test_arm.py                # 机械臂动作单元测试
│   ├── test_calibration.py        # 标定数据准确性测试
│   ├── test_camera.py             # 摄像头画面读取测试
│   ├── test_racks.py              # 货架/槽位点位测试
│   ├── tool_fine_tune.py          # [关键工具] 14点位微调工具 (含 J6 旋转调节)
│   └── tool_get_coords.py         # 快速获取当前机械臂坐标工具
│
├── 📂 web/                        # [前端资源] Web 控制台界面
│   ├── 📂 static/                 # 静态资源
│   │   ├── 📂 css/                # 样式文件 (style.css)
│   │   └── 📂 js/                 # 脚本文件 (app.js - 含语音识别与流式交互逻辑)
│   └── 📂 templates/              # HTML 模板
│       └── index.html             # 主控制台页面 (Bootstrap 布局)
│
├── .gitignore                     # Git 忽略文件配置
├── gen_tree.py                    # 目录结构生成脚本
├── LICENSE                        # 开源许可证
├── main.py                        # [程序入口] 主程序启动文件 (多线程调度中心)
├── README.md                      # 项目主说明文档 (英文)
├── README_cn.md                   # 项目主说明文档 (中文)
└── requirements.txt               # Python 项目依赖列表
```

---

## 相关设置

本项目一共三台设备，设备主机设置如下：

1号主机：ZC-Coffee-01

```bash
user.email=coffee_sort_01@zhicheng.com
user.name=ZC-Coffee-01
```

2号主机：ZC-Coffee-02

```bash
user.email=coffee_sort_02@zhicheng.com
user.name=ZC-Coffee-02
```

3号主机：ZC-Coffee-03
```bash
user.email=coffee_sort_03@zhicheng.com
user.name=ZC-Coffee-03
```


## 🔧 常见问题 (FAQ)

**Q: 点击“复位”机械臂没反应？**
A: 检查 `config/settings.py` 中的串口号是否正确。如果机械臂完全下垂，程序会自动发送 `power_on` 指令，请等待 1-2 秒充能。

**Q: AI 回复了但机械臂不动？**
A: 检查 Web 界面右侧的 **库存状态**。如果目标槽位显示【已满】，系统会触发安全拦截机制，拒绝执行放置动作。请先点击“清空库存”。

**Q: 摄像头画面是黑的？**
A: 请在 `main.py` 中检查 `cv2.VideoCapture(0)` 的索引号，如果有多个摄像头，尝试改为 1 或 2。

---

## 📄 许可证 (License)

Copyright (c) 2026 Hangzhou Zhicheng Technology Co., Ltd. All Rights Reserved.

本项目为 **杭州智珵科技有限公司** 专有软件。
未经书面授权，严禁复制、分发、修改或用于商业用途。详情请参阅根目录下的 [LICENSE](LICENSE) 文件。

This project is proprietary software of **Hangzhou Zhicheng Technology Co., Ltd.**
Unauthorized copying, distribution, modification, or commercial use is strictly prohibited. See the [LICENSE](LICENSE) file for details.

---

> **致谢**：本项目基于 pymycobot 和 OpenCV 开发，AI 能力由 Qwen 提供支持。