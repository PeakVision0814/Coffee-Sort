# Git 版本控制系统：工业应用指南

## Git 是什么？

在工业自动化、嵌入式开发或上位机软件工程中，Git 不仅仅是一个“写代码”的工具，它是一个**工程资产的保险柜与时光机**。

**1. 核心定义**
Git 是目前世界上最先进的**分布式版本控制系统**。不同于传统的“复制粘贴备份法”（如 `项目_最终版.zip`、`项目_最终版_再改.zip`），Git 能精确记录文件内容的每一次变动。

**2. 工业场景下的价值**

* **故障追溯（Traceability）：** 当产线设备因程序更新出现故障时，Git 能精确告诉你：**谁**在**什么时间**修改了**哪一行**代码或参数。
* **版本回滚（Rollback）：** 遇到严重 Bug，可以一键将工程退回到昨天（或任意历史时间点）的稳定状态，极大降低停机风险。
* **多人协作（Collaboration）：** 允许多位工程师同时开发同一个项目（例如一人写 PLC 通讯，一人写界面），最后通过自动合并功能整合在一起，避免文件覆盖冲突。
* **分布式安全（Security）：** 每个工程师的电脑上都有一份完整的项目历史备份。即使服务器崩溃，任何一台工作站都能恢复所有数据。

---

## Windows 环境标准化安装教程

工业现场通常使用 Windows 10/11 或 Windows Server 系统。以下是基于 Windows 的标准部署流程。

### 1. 获取安装包

* **外网环境：** 访问 Git 官方网站 [git-scm.com](https://git-scm.com/download/win)。
* **内网/涉密环境：** 请从安规部门许可的介质中获取 `Git-xxx-64-bit.exe` 安装文件。
* *建议下载 64位 Standalone Installer（独立安装包）。*


### 2. 安装步骤详解

双击安装包，运行安装向导。大部分步骤保持默认即可，但以下**关键节点**必须按说明配置，以免影响后续工具（如 VS Code, PyCharm）的调用。

**步骤 1：许可协议 (Information)**

![](img\ScreenShot_2026-02-05_140648_073.png)

* 直接点击 **Next**。

**步骤 2：选择安装位置 (Select Destination Location)**

* 建议保持默认路径 `C:\Program Files\Git`。
* *注意：工业软件路径建议避免中文名称。*

**步骤 3：选择组件 (Select Components)**

* 保持默认勾选。
* 建议勾选 **"On the Desktop"** (在桌面创建图标)，方便快速打开。

**步骤 4：选择默认编辑器 (Choosing the default editor used by Git)**

* 默认通常是 Vim（操作难度极大）。
* **强烈建议修改：** 如果电脑装有 Notepad++ 或 VS Code，请在下拉菜单中选择。如果没有，请选择 **Use Notepad as Git's default editor**（使用记事本），这对非专职程序员最友好。

**步骤 5：调整初始分支名 (Adjusting the name of the initial branch in new repositories)**

* 选择第二个选项：**Override the default branch name for new repositories**。
* 填入：`main`（这是目前国际通用的标准主分支名称）。

**步骤 6：配置环境变量 (Adjusting your PATH environment)** —— **【关键步骤】**

* **必须选择中间项：** `Git from the command line and also from 3rd-party software`。
* *解释：* 这允许你在 CMD、PowerShell 以及 VS Code 等第三方工业软件中直接调用 Git，而不必局限于 Git 专用的黑框框。

**步骤 7：选择 SSH 可执行文件 (Choosing the SSH executable)**

* 保持默认：`Use bundled OpenSSH`。

**步骤 8：配置行尾符号转换 (Configuring the line ending conversions)** —— **【关键步骤】**

* 选择第一项：`Checkout Windows-style, commit Unix-style line endings`。
* *解释：* Windows 和 Linux/Unix 系统对“换行”的定义不同。此选项能自动处理这种差异，防止代码在不同系统间传输时出现格式错误。

**步骤 9：配置终端模拟器 (Configuring the terminal emulator...)**

* 建议选择第一项：`Use MinTTY (the default terminal of MSYS2)`。
* MinTTY 的界面操作体验优于 Windows 自带的 CMD。

**步骤 10：后续选项**

* 后续步骤（Git Credential Manager, File System Caching 等）全部保持**默认**，一路点击 **Next** 直到 **Install**。

---

## 初始配置

安装完成后，不能直接使用。必须进行**身份注册**，这是为了保证工程变更的可追溯性。

**1. 打开终端**

* 在桌面右键点击空白处，选择 `Open Git Bash here`（如果安装了）或者直接打开 CMD。

**2. 配置用户信息（必做）**
在命令行中依次输入以下两条命令（注意空格，可以将引号内的内容替换为实际信息）：

```bash
# 配置用户名（建议使用工号或拼音全名，方便追责与查询）
git config --global user.name "Huang_Gong_007"

# 配置邮箱（建议使用公司工作邮箱）
git config --global user.email "huang.gong@example.com"
```

* `--global` 参数意味着这台电脑上所有的 Git 项目都默认使用这个身份。

**3. 验证配置**
输入以下命令查看配置列表，确认上述信息已生效：

```bash
git config --list
```

如果你在列表中看到了 `user.name` 和 `user.email` 且内容正确，说明环境搭建完成。

---

## 常用指令速查卡（工业极简版）

对于日常工程维护，掌握以下 6 个命令即可覆盖 90% 的场景：

1. **`git init`**
* *作用：* 初始化。把当前文件夹变成一个 Git 仓库（开始监控该文件夹）。


2. **`git status`**
* *作用：* 检查状态。看看哪些文件被修改了，哪些还没被记录。


3. **`git add .`**
* *作用：* 暂存。把所有修改过的文件放到“发货区”（准备提交）。


4. **`git commit -m "备注信息"`**
* *作用：* 提交存档。生成一个永久的版本节点。
* *范例：* `git commit -m "修复了机械臂归零坐标偏移的问题"`


5. **`git log`**
* *作用：* 查看日志。查看历史提交记录（谁，什么时候，改了什么）。


6. **`git clone [地址]`**
* *作用：* 克隆。从服务器（如 GitLab/Gitea）把项目完整下载到本地。

---

## 常见问题与注意事项

1. **不要把所有东西都塞进 Git：**
* 编译生成的临时文件（如 `.exe`, `.obj`, `.log`）不需要版本控制。请在项目根目录创建一个名为 `.gitignore` 的文件，在里面列出要忽略的文件后缀。


2. **二进制文件管理：**
* Word 文档、CAD 图纸、PLC 的编译后文件属于二进制文件。Git 虽然能存储，但无法像代码一样显示“具体改了哪一行文字”。对于此类文件，Git 主要起备份和版本回滚作用。


3. **网络问题：**
* 如果拉取代码速度极慢（GitHub），请考虑配置代理或使用国内代码托管平台（如 Gitee）或企业内网搭建的 GitLab。