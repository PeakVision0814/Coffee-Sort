这是一个非常必要的步骤！

现在的系统已经从一个简单的“脚本程序”进化成了一个**“B/S架构的 AI 工业控制系统”**。新的 README 需要重点体现：Web 指挥端、AI 大模型集成、仿真开发模式以及**定点盲抓**的新逻辑。

以下是为您重写的 `README.md`。您可以直接复制使用，或者根据实际情况微调。

---

# ☕ Coffee Sort Pro (AI-Powered)

> **v3.2 AI Commander Edition**
> 结合 **大语言模型 (LLM)** + **机器视觉** + **Web控制台** 的智能咖啡分拣指挥系统。

## 📖 项目简介

**Coffee Sort Pro** 是一个现代化的工业分拣解决方案。与传统的示教编程不同，本项目引入了 **AI 指挥官 (AI Commander)** 概念。

用户可以通过**自然语言**（如“把红色盒子放到1号位”或“开启自动分拣”）与系统交互。系统采用 **Web 无头模式 (Headless)** 运行，自动启动浏览器控制台，支持**仿真模式 (Simulation)**，允许在没有机械臂硬件的情况下进行全流程逻辑开发。

### 🌟 核心特性

* **🧠 AI 指挥核心**: 集成 DeepSeek/OpenAI API，支持自然语言解析指令。
* **💻 Web 驾驶舱**: 现代工业风 UI，支持视频监控、库存可视化、参数热配置。
* **🎮 虚实双模**:
* **仿真模式**: 内置虚拟机械臂与虚拟相机，在家也能开发业务逻辑。
* **实机模式**: 驱动 myCobot 280 完成物理分拣。


* **🛡️ 稳健控制**: 采用“定点盲抓 + 视觉触发”策略，配合闭环位置检测，确保工业级稳定性。
* **💓 安全机制**: 浏览器心跳检测（关闭页面自动停机）、操作互斥锁（自动模式下禁用 AI）。

---

## 🛠️ 快速开始

### 1. 环境准备

确保已安装 [Git](docs/Environment%20Setup/git.md) 和 [Anaconda](docs/Environment%20Setup/Anaconda.md)。

```bash
# 克隆项目
git clone https://github.com/PeakVision0814/Coffee-Sort.git
cd Coffee-Sort

# 创建并激活环境
conda create -n coffee_sort python=3.10
conda activate coffee_sort

# 安装依赖
pip install -r requirements.txt
```

### 2. 模式配置

打开 `config/settings.py`，根据当前环境修改开关：

```python
# True = 使用虚拟硬件，无需连接机械臂
# False = 现场部署
SIMULATION_MODE = True 
```

### 3. 启动系统

```bash
python main.py
```

* 系统启动后会自动打开默认浏览器访问 `http://127.0.0.1:5000`。
* **仿真模式下**：您会看到带有 "SIMULATION" 水印的视频流，可以直接点击按钮或对话测试逻辑。
* **实机模式下**：请确保机械臂已上电且 USB 连接正常。

---

## 🖥️ Web 指挥台使用说明

### 🤖 1. AI 交互 (左侧面板)

* **对话控制**：在输入框输入自然语言，例如：
* *"启动自动分拣"*
* *"复位机械臂"*
* *"清空所有库存状态"*


* **配置 AI**: 点击右上角 **"⚙️ 设置"** 按钮，可在线修改 API Key、模型名称 (DeepSeek/OpenAI/Custom) 和提示词，配置自动保存至本地。

### 📊 2. 硬件监控 (右侧面板)

* **实时画面**: 显示摄像头捕获的作业区域。
* **库存状态**: 6个槽位的占用情况 (Free/Full)。
* **互斥控制**:
* 🟢 **绿色按钮**: 启动自动流水线（点击后 AI 将被锁定，防止干扰）。
* 🔴 **红色按钮**: 暂停流水线（点击后恢复 AI 控制权）。



---

## 📂 项目结构 (Updated)

```text
coffee_sort/
├── config/                 # [配置中心]
│   ├── settings.py         # 核心参数 (仿真开关、坐标、端口)
│   └── ai_config.json      # AI API 密钥配置 (由 Web 端自动读写)
├── modules/                # [后端核心]
│   ├── ai_decision.py      # AI 大模型接口封装
│   ├── arm_control.py      # 机械臂驱动 (含 Mock 虚拟驱动)
│   ├── mock_hardware.py    # 虚拟硬件实现 (仿真模式核心)
│   ├── vision.py           # 视觉算法
│   └── web_server.py       # Flask 后端服务
├── web/                    # [前端资源]
│   ├── static/             # CSS / JS / 图片
│   └── templates/          # HTML 页面
├── scripts/                # [调试工具]
├── main.py                 # [启动入口] 无头模式主程序
└── requirements.txt        # 依赖列表
```

---

## 相关设置

本项目一共三台设备，设备主机设置如下：

1号主机：ZC-Coffee-03

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

## ⚙️ 技术细节

### 为什么选择“定点盲抓”？

在早期版本中，我们尝试使用视觉计算动态坐标。但在实际产线中，传送带末端和槽位的位置是物理固定的。为了消除视觉识别带来的抖动误差，v3.0 版本采用了更稳健的策略：

1. **视觉**仅作为**“触发器”** (Trigger)：告诉系统“这里有东西”。
2. **机械臂**执行**“预设动作”** (Action)：前往 `settings.py` 中经过校准的绝对坐标进行抓取。

### 安全机制

* **心跳保活**: 前端每秒发送心跳包。若浏览器关闭或网络断开超过 3 秒，Python 后端自动安全退出，防止失控。
* **粗颗粒度暂停**: 点击暂停时，机械臂会**完成当前正在进行的抓取动作**后再停止，避免物体悬空掉落。

---

## 📅 更新日志

* **v3.2 (Current)**: UI 重构，AI 指挥中心风格；实现自动/AI模式严格互斥；增加 AI 参数热配置功能。
* **v3.1**: 引入无头模式 (Headless) 与浏览器自动启动；增加心跳检测。
* **v3.0**: 重构底层运动逻辑，由视觉引导转向定点盲抓；增加仿真模式。

---

## 📞 联系方式

**Project Lead**: 黄高朋
**Status**: 🚀 Active Development