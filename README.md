# ☕ Coffee Sort - Smart Robotic Arm Sorting System

English | [简体中文](README_cn.md)

> **Coffee Sort** is an intelligent sorting platform integrating **Computer Vision (CV)**, **Large Language Models (LLM)**, **Robot Control**, and **Industrial PLC Automation**.
> It not only "understands human language" and "perceives the environment", but also features industrial-grade software/hardware foolproof mechanisms and an emergency stop system, achieving a true deep integration of IT (Information Technology) and OT (Operational Technology).

---

## ✨ Key Features

### 🧠 1. AI Semantic Brain

* **Natural Language Interaction**: Integrates LLMs (supports DeepSeek, OpenAI, etc.), processing fuzzy commands (e.g., "Take away that yellow thing", "Clear the inventory").
* **Intent Parsing & Interception**: The AI automatically extracts JSON commands. The system features logical interception capabilities; when an unsupported color or a full target slot is detected, the AI will reject the action and prompt the user via voice.

### 🏭 2. Industrial-Grade Security & PLC Linkage

* **Ethernet Inventory Synchronization**: Direct connection to the underlying PLC via Ethernet based on the Snap7 protocol, reading the real physical inventory status of the 6 slots in milliseconds.
* **G35 Dynamic Hardware Emergency Stop**: A start permission signal controlled by the PLC (with 0.5s software debouncing). The robotic arm is monitored in real-time during high-risk picking/placing operations. If the signal is lost, it locks in place instantly (E-STOP).
* **G36 Physical Anti-Collision Reset**: The dangerous software reset function is disabled, fully delegating control to the operator by long-pressing the physical red button (G36) on the machine. The system automatically calculates the nearest safe waypoint and executes a "smart anti-collision pathfinding" for safe homing.

### 👁️ 3. Visual Perception

* **Color & Contour Recognition**: Accurately identifies objects of specified colors (default: red, yellow, silver).
* **Dynamic Coordinate Mapping**: Automatically converts the camera's pixel coordinates $(u, v)$ into the robotic arm's physical space coordinates $(x, y, z)$.

### 🗣️ 4. Multimodal Command Center

* **Voice Commands**: Based on the browser's native Web Speech API, enabling natural language dialogue with one click. The system automatically records operation logs and chat history.
* **Web Console**: A modern dashboard built with Flask, supporting real-time video stream monitoring, status overview, and global automation start/stop.

---

## 🛠️ Hardware Requirements

* **Robotic Arm**: Elephant Robotics **myCobot 280 M5**.
* **PLC**: Industrial PLC supporting the S7 protocol (e.g., Siemens S7-1200), default IP `192.168.0.10`.
* **Camera**: Standard USB Camera.
* **End Effector**: Pneumatic Suction Pump / Gripper.
* **Computing Platform**: Windows / Linux / macOS.

---

## 🚀 Quick Start

### 1. Environment Setup

For detailed steps, please refer to the [📚 Environment Setup Guide](https://www.google.com/search?q=./docs/Environment%2520Setup/README.md).

```bash
# Clone the repository
git clone https://github.com/YourUsername/coffee_sort.git
cd coffee_sort

# Creating a virtual environment is recommended
conda create -n coffee_sort python=3.10
conda activate coffee_sort

# Install dependencies
pip install -r requirements.txt

```

### 2. Configuration

1. **AI Configuration**:
Copy the example file and enter your API Key.

```bash
cp config/ai_config.json.example config/ai_config.json

```

2. **Hardware Configuration**:
Open `config/settings.py` and modify `PORT` to your robotic arm's serial port (e.g., `COM3` or `/dev/ttyUSB0`).

### 3. Start the System

Ensure the robotic arm is powered on and the PLC network cable is connected, then run:

```bash
python main.py

```

The system will automatically perform an initial homing. Once the terminal displays `Web Console Started`, visit `http://127.0.0.1:5000` in your browser to enter the command center.

---

## 🎮 Operation Guide

* **Start Automatic Pipeline**: Click "Start Automatic Sorting" on the Web interface, or say "Start the pipeline" to the AI. After the camera detects an object and the PLC provides the G35 permission signal, the robotic arm will automatically grab it and find an empty slot to place it.
* **Single AI Sorting**: Say "Put the red one in slot 2" to the AI.
* **Exception Handling & Reset**: If an unexpected situation occurs and G35 is disconnected triggering a physical E-stop, please clear the site, then **long-press the red reset button (G36) on the machine for 3 seconds**. The robotic arm will automatically bypass obstacles and return to the home position.

---

## 📂 Project Structure

```text
coffee_sort/
├── 📂 config/                 # [Config Center] Hardware, vision, and AI parameters
│   ├── ai_config.json         # AI API Keys and System Prompts
│   ├── settings.py            # Core constants (Serial ports, GPIO pins, Waypoints)
│   └── vision_config.json     # Vision HSV thresholds and ROI areas
│
├── 📂 docs/                   # [Doc Center] Environment setup & myCobot official manuals
│
├── 📂 logs/                   # [Log Center] 
│   ├── system.log             # Core system execution logs (Rolling supported)
│   └── chat_history.json      # History of conversations between the user and AI
│
├── 📂 modules/                # [Core Architecture] Backend business logic modules
│   ├── ai_decision.py         # AI decision making and streaming command parsing
│   ├── arm_control.py         # Robotic arm control (Closed-loop, G35/G36 E-Stop monitoring)
│   ├── plc_comm.py            # Snap7 PLC Ethernet communication module
│   ├── vision.py              # OpenCV image processing and eye-in-hand coordination
│   └── web_server.py          # Flask Web routing and video streaming service
│
├── 📂 tools/                  # [Engineering Tools] Debugging and calibration scripts
│   ├── calibrate_camera.py / calibrate_eye.py  # Camera distortion & Hand-eye calibration
│   ├── calibrate_vision.py    # Visual HSV threshold slider debugging tool
│   ├── test_gpio.py           # [Diagnostic] Low-level GPIO pin level reading test
│   ├── tool_fine_tune.py      # [Calibration] 6-axis spatial waypoint fine-tuning tool
│   └── ...                    # Other automated unit tests and interactive scripts
│
├── 📂 web/                    # [Front-End] UI resources
│   ├── static/css & js        # Styling and interactive logic (Speech recognition, DOM)
│   └── templates/index.html   # Command center main control panel
│
├── main.py                    # [Main Controller] System entry & multi-thread dispatcher
└── requirements.txt           # Python dependency list

```

---

## 💻 Relevant Settings (Git Environment)

The Git configurations for the resident test machines of this project are as follows:

**Host 1: ZC-Coffee-01**

```bash
git config user.name "ZC-Coffee-01"
git config user.email "coffee_sort_01@zhicheng.com"

```

**Host 2: ZC-Coffee-02** / **Host 3: ZC-Coffee-03** (Configurations follow the same pattern)

---

## 🔧 FAQ

**Q: Why does the robotic arm suddenly lock up halfway and report `E-STOP`?**
A: The system detected that the G35 start permission signal dropped (level changed to 0). This is a physical-level emergency stop protection. Please check if the PLC actively cut off the signal, or if the jumper wires are loose. Once safety is restored, long-press the G36 button for 3 seconds to execute a reset.

**Q: Why can't I execute a reset command via the AI prompt?**
A: To comply with industrial equipment safety standards, the software reset permission has been completely removed. All homing operations must be triggered by the operator via the physical machine button (G36) after confirming safety on-site.

**Q: The camera video is lagging or black?**
A: Please check the device index for `cv2.VideoCapture(0)` in `main.py`, and ensure the USB power supply is sufficient and not occupied by other programs.

---

## 📄 License

Copyright (c) 2026 Hangzhou Zhicheng Technology Co., Ltd. All Rights Reserved.

This project is proprietary software of **Hangzhou Zhicheng Technology Co., Ltd.**
Unauthorized copying, distribution, modification, or commercial use is strictly prohibited. See the `LICENSE` file in the root directory for details.