# ☕ 咖啡智能化分拣系统 (Coffee Sorting System)

> 基于 myCobot 280 机械臂与机器视觉的自动化分拣解决方案。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Hardware](https://img.shields.io/badge/Hardware-myCobot%20280-green)](https://www.elephantrobotics.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red)]()

## 📖 项目简介

本项目旨在实现咖啡胶囊/咖啡盒的自动化识别与分拣。系统利用 **OpenCV** 进行视觉定位，通过 **pymycobot** 控制六轴机械臂，实现“眼在手”(Eye-in-Hand) 的抓取作业。项目采用 Python 原生架构，支持与 PLC 进行 IO 信号交互（开发中）。

---

## 🛠️ 硬件环境

1.  **机器人**: Elephant Robotics myCobot 280 M5 (2023款)
2.  **视觉传感器**: USB 免驱广角摄像头 (安装于机械臂末端/法兰)
3.  **末端执行器**: 气动夹爪 / 吸泵 (当前代码已预留接口)
4.  **计算平台**: Windows 10/11 PC (推荐)
5.  **周边**: 传送带、光电传感器、12V 电源适配器

---

## 📦 基础环境准备 (新手必读)

如果你是第一次在电脑上运行此程序，请先安装以下两个基础工具：

### 1. 安装 Git (用于下载代码)
* **下载地址**: [https://git-scm.com/download/win](https://git-scm.com/download/win)
* **安装步骤**:
    1.  点击链接下载 `64-bit Git for Windows Setup`。
    2.  双击运行安装包。
    3.  **一路点击 "Next" (下一步)** 直到完成即可，无需修改默认设置。

### 2. 安装 Miniconda (用于管理 Python 环境)
* **下载地址**: [https://docs.anaconda.com/miniconda/](https://docs.anaconda.com/miniconda/)
* **安装步骤**:
    1.  下载 `Windows 64-bit` 安装包。
    2.  安装过程中，建议**勾选** "Add Miniconda3 to my PATH environment variable" (虽然它显示红色警告，但这能让你在任何终端直接使用 conda，方便新手)。
    3.  如果不勾选，请在安装完成后，通过开始菜单打开 **"Anaconda Prompt"** 来输入后续命令。

---

## 💻 软件安装与配置

完成上述基础准备后，请按以下步骤部署项目：

### 1. 克隆仓库
打开终端 (CMD 或 PowerShell)，输入以下命令下载项目代码：
```bash
git clone https://github.com/PeakVision0814/Coffee-Sort.git
cd Coffee-Sort
```

### 2. 创建虚拟环境 (推荐)

为了防止环境冲突，我们创建一个独立的 Python 3.10 环境：

```bash
conda create -n coffee_sort python=3.10
conda activate coffee_sort
```

*(注意：每次重新打开终端运行项目前，都需要执行 `conda activate coffee_sort`)*

### 3. 安装依赖库

```bash
pip install -r requirements.txt
```

---

## 📂 项目结构

```text
coffee_sort/
├── config/                 # [配置中心]
│   ├── settings.py         # 核心配置文件 (端口、坐标、高度)
│   ├── calibration.json    # 手眼标定结果 (自动生成)
│   └── camera_matrix.npz   # 相机畸变内参 (自动生成)
├── docs/                   # [参考文档库]
│   ├── 1. 产品信息/        # 产品简介与参数
│   ├── 2. 基础设置/        # 故障排查与安装
│   ├── 3. 功能与引用/      # 包含 Python/ROS/C++ 等详细 API 开发指南
│   └── ...
├── logs/                   # [日志与数据]
│   └── calibration_imgs/   # 存放相机标定过程中拍摄的棋盘格图片
├── modules/                # [核心代码模块]
│   ├── ai_decision.py      # AI 决策模块 (DeepSeek 接口预留)
│   ├── arm_control.py      # 机械臂运动控制封装 (抓取/放置逻辑)
│   ├── plc_comm.py         # PLC 通信模块 (IO 信号交互)
│   └── vision.py           # 视觉算法核心 (去畸变、识别、坐标换算)
├── scripts/                # [调试工具箱]
│   ├── calibrate_camera.py # 工具: 采集棋盘格并计算内参
│   ├── calibrate_eye.py    # 工具: Eye-in-Hand 手眼标定
│   ├── tool_get_coords.py  # 工具: 机械臂可视化示教器 (获取坐标)
│   └── test_*.py           # 各类硬件单元测试脚本
├── main.py                 # [主程序] 系统启动入口
├── requirements.txt        # Python 依赖库列表
├── 开发路线.md             # 项目阶段规划表
└── README_cn.md            # 项目说明文档

```

---

## 🚀 快速开始指南

### 步骤一：硬件连接

1. 连接机械臂 USB Type-C 至电脑，确认端口号（如 `COM3`）。
2. 连接 USB 摄像头。
3. 接通机械臂 12V 电源。

### 步骤二：基础检查

运行硬件测试脚本，确认通信正常：

```bash
python scripts/test_arm.py
```

### 步骤三：系统标定 (初次部署必做)

1. **相机去畸变标定** (需要棋盘格):
```bash
python scripts/calibrate_camera.py
```


2. **手眼标定** (计算像素与毫米关系):
```bash
python scripts/calibrate_eye.py
```


*按提示操作机械臂对准参照物，结果将自动保存至 `config/calibration.json`。*

### 步骤四：参数配置

使用示教器工具获取现场坐标：

```bash
python scripts/tool_get_coords.py
```

* 按 `R` 解锁拖动，按 `L` 锁定，按 `P` 打印坐标。
* 将获取的 **观测点(Observe Pose)**、**抓取高度(Pick Z)**、**仓库坐标(Bin Coords)** 填入 `config/settings.py`。

### 步骤五：运行主程序

```bash
python main.py
```

* 程序启动后，机械臂将自动前往观测点。
* 当视觉识别到目标（红框锁定）时，**按下空格键** 触发自动抓取。
* 按 `Q` 键或点击窗口关闭按钮退出。

---

## ⚠️ 注意事项

1. **安全第一**: 调试期间请务必**手扶电源开关**，遇到撞机风险立即断电。
2. **坐标系方向**: 如果在 `vision.py` 测试中发现物体移动方向与数值变化相反，请修改代码中的 `dx_mm` 或 `dy_mm` 正负号。
3. **夹爪状态**: 目前代码中 `gripper_open` 和 `gripper_close` 均为模拟延时，待硬件到货后需接入实际 IO 控制指令。

---

## 📅 开发进度 (Roadmap)

* [x] 硬件链路通信 (Python -> Robot)
* [x] 视觉看门狗与去畸变算法
* [x] Eye-in-Hand 手眼标定系统
* [x] 坐标系转换与自动抓取逻辑
* [ ] 3D 打印夹爪安装与调试 (等待硬件)
* [ ] PLC IO 信号握手 (下一步计划)
* [ ] DeepSeek AI 语音指令集成

---

## 📞 联系方式

**技术负责人**: 黄高朋
**项目**: COFFEE-SORTING-2026