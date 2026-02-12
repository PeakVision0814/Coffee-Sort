# 🛠️ 开发环境配置指南 (Environment Setup)

欢迎来到 **智能机械臂分拣系统** 的环境配置指南。本项目依赖 Python 视觉处理、AI 大模型接口以及机械臂控制库。为了确保项目顺利运行，请按照以下顺序完成开发环境的搭建。

---

## 📋 配置流程概览

1.  **安装版本控制工具 (Git)**：用于拉取和管理代码。
2.  **安装 Python 环境管理工具 (Anaconda)**：用于创建独立的虚拟环境，避免依赖冲突。
3.  **创建虚拟环境**：配置本项目专属的 Python 运行环境。
4.  **安装项目依赖**：安装 `requirements.txt` 中的第三方库。
5.  **硬件驱动安装**：确保电脑能识别机械臂串口。

---

## 1. 安装 Git (版本控制)

Git 是本项目代码同步和管理的必要工具。

* **详细教程**：请阅读 [📄 Git 安装与配置指南](./git.md)
* **验证方法**：
    打开终端（CMD/PowerShell），输入：
    ```bash
    git --version
    ```

---

## 2. 安装 Python 环境 (推荐 Anaconda)

强烈建议使用 **Anaconda** 或 **Miniconda** 来管理 Python 环境。它可以帮我们轻松解决 OpenCV、PyTorch 等复杂库的依赖问题。

* **详细教程**：请阅读 [📄 Anaconda 安装指南](./Anaconda.md)
* *(备选方案)*：如果你坚持使用原生 Python，请参考 [📄 Python 原生安装指南](./python.md)

---

## 3. 初始化项目环境

完成上述软件安装后，请按照以下步骤配置本项目的运行环境：

### 3.1 克隆项目 (如果尚未下载)
```bash
git clone https://github.com/YourUsername/coffee_sort.git
cd coffee_sort
```