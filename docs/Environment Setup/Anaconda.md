# Anaconda 发行版与 Conda 包管理系统：工业级 Python 环境部署指南

## 第一部分：为什么工业场景首选 Anaconda？

在工业现场（工控机、上位机）或研发实验室中，我们经常面临以下痛点：

1. **环境冲突**：老项目用的是 Python 3.7 和旧版 TensorFlow，新项目要用 Python 3.10 和 PyTorch。如果装在一起，系统会崩溃。
2. **离线安装难**：许多工业内网无法连接外网，手动去下载几百个依赖包（如 NumPy, SciPy）极其痛苦且容易报错。
3. **配置繁琐**：安装科学计算库通常需要编译 C++ 底层，Windows 上极易失败。

**Anaconda 完美解决了上述问题：**

* **全家桶 (All-in-One)**：安装包里已经预装了 Python 解释器以及 180+ 个最常用的科学计算、数据分析和工程绘图包。开箱即用。
* **虚拟环境 (Virtual Environments)**：它允许你创建多个**相互隔离的“平行宇宙”**。你可以在“宇宙A”里跑老代码，在“宇宙B”里开发新功能，互不干扰。
* **Conda 指令**：比 pip 更强大的包管理器，能处理非 Python 的依赖（如 CUDA、MKL 数学库）。

---

## 第二部分：下载与安装 (Windows)

由于 Anaconda 安装包较大（约 600MB+），官方服务器在国外，下载极慢。

### 1. 获取安装包

* **推荐下载地址（清华大学镜像站）：**
[https://mirrors.tuna.tsinghua.edu.cn/anaconda/archive/](https://mirrors.tuna.tsinghua.edu.cn/anaconda/archive/)
* **版本选择：**
* 请按日期排序，拉到最下方下载**最新版**。
* 文件名格式通常为：`Anaconda3-202x.xx-Windows-x86_64.exe`。



### 2. 安装步骤详解（SOP）

双击运行安装包，按照以下流程操作：

**步骤 1：许可与用户 (Select Installation Type)**

* 选择 **Just Me (recommended)**。
* *解释：* 这样安装不需要管理员权限，且不会干扰系统里其他用户的配置，减少权限报错。

**步骤 2：安装路径 (Choose Install Location)**

* **强烈建议：** 不要安装在 C 盘（因为很大），也不要安装在**包含中文或空格**的路径下。
* *推荐路径：* `D:\Anaconda3` 或 `D:\Softwares\Anaconda3`。

**步骤 3：高级选项 (Advanced Options) —— 【关键决策】**
安装界面会有两个复选框，请按如下建议勾选：

1. 🔲 **Add Anaconda3 to my PATH environment variable**
    * **建议：不勾选**（或者该选项显示为红色）。
    * *原因：* 自动添加环境变量可能会与你电脑里已有的其他软件（如 MinGW, 之前的 Python）冲突。我们将使用 `conda init` 这种更现代、更安全的方式来配置（见第四部分）。


2. ✅ **Register Anaconda3 as my default Python 3.x**
    * **建议：勾选**。
    * *原因：* 让 VS Code 或 PyCharm 等编辑器能自动检测到它。



点击 **Install** 等待安装完成（可能需要几分钟）。最后点击 **Finish**（可以取消勾选 "Tutorial" 相关的选项）。

---

## 第三部分：初始化配置（让 CMD/PowerShell 识别 Conda）

安装完成后，你需要进行一次性配置，以便在常用的终端（CMD, PowerShell）中直接使用 `conda` 命令。

1. **打开 Anaconda 专用终端**：
* 在 Windows 开始菜单中找到文件夹 `Anaconda3 (64-bit)`。
* 点击 **Anaconda Prompt (Anaconda3)**。


2. **执行初始化命令**：
在打开的黑框框中，输入以下命令并回车：
```bash
conda init cmd.exe
conda init powershell
```

3. **生效**：
* 关闭当前窗口。
* **重新打开**一个新的 CMD 或 PowerShell 窗口。
* 如果你看到命令行最前面出现 **`(base)`** 字样，说明配置成功！

---

## 配置国内镜像源（加速下载）

为了在工业内网或国内网络下流畅下载包，必须将下载源指向国内服务器（如清华源、阿里源）。

在 CMD 或 PowerShell 中依次执行以下命令：

```bash
# 添加清华镜像源
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/

# 设置搜索时显示通道地址
conda config --set show_channel_urls yes
```

---

## 第五部分：核心操作手册（工程人员必会）

在日常开发中，请严格遵守**“一项目一环境”**的原则。

### 1. 创建环境（建厂房）

假设你要做一个机器视觉分拣项目，建议创建一个专属环境：

```bash
# 格式：conda create -n [环境名] python=[版本号]
conda create -n vision_sort python=3.10
```

*系统会询问是否继续，输入 `y` 回车。*

### 2. 激活环境（进车间）—— **最重要的一步**

在安装库或运行代码前，必须先激活对应的环境。

```bash
conda activate vision_sort
```

*成功后，命令行前缀会从 `(base)` 变为 `(vision_sort)`。*

### 3. 安装依赖包（进设备）

```bash
# 方式一：使用 conda 安装（推荐用于 numpy, opencv 等底层库）
conda install numpy pandas opencv

# 方式二：使用 pip 安装（conda 找不到的包用 pip）
pip install pymycobot
```

### 4. 退出环境（下班）

```bash
conda deactivate
```

### 5. 查看与删除

```bash
# 查看所有环境
conda env list

# 删除环境（慎用）
conda remove -n vision_sort --all
```

---

## 常见问题排查

**Q1: PowerShell 提示“无法加载文件...profile.ps1，因为在此系统上禁止运行脚本”**

* **原因**：Windows 安全策略限制。
* **解决**：以管理员身份运行 PowerShell，输入 `Set-ExecutionPolicy RemoteSigned`，选择 `Y`。

**Q2: 安装包时速度极慢或连接失败**

* **解决**：检查是否已配置国内镜像源（见第四部分）。如果公司内网有防火墙，可能需要联系 IT 部门设置代理，或使用离线安装包。

**Q3: 那个 `(base)` 看着很烦，能默认关闭吗？**

* **解决**：如果你不希望每次打开终端都自动激活 base 环境，可以输入：
`conda config --set auto_activate_base false`
*这样以后就需要手动输入 `conda activate` 才会进入环境。*