# Corning PLC 工业表格通用微内核套件与规范化工作流
## (Industrial PLC Table Microkernel Toolkit & Workflow v2.0)

> **适用项目**：美国康宁 (Corning Incorporated) CT173 项目 (1-封边机 / 2-撕胶带机 / 3-修边机)  
> **核心标准**：《IEC 61131-3 国际工控编程标准》、《电气术语定义标准与命名规范》  
> **运行平台**：Windows 11 / Windows 10 (x64) | 汇川 InoProShop (CODESYS V3.5) / AutoShop

---

## 一、 快速启动与接入入口 (Quick Start)

本套件提供 **5 大标准化接入入口**，满足不同工程师角色与工业场景需求：

> 💡 **路径提示**：如果您在项目总工程目录 `PLC+HMI程序` 下，可直接双击根目录下的 `启动_桌面GUI工具.bat` 或 `启动_Web控制台.bat`；如果您已 `cd 自动翻译与规范化工具_Workflow`，请使用以下对应相对路径：

### 1. 桌面可视化 GUI (推荐现场人员使用)
- **直接双击运行**：
  - 在本目录下：双击 [`run_gui.bat`](run_gui.bat)
  - 在总工程根目录下：双击 `启动_桌面GUI工具.bat`
- **命令行启动**：
  - 本目录下：`python core/plc_gui.py`
  - 总工程目录下：`python 自动翻译与规范化工具_Workflow/core/plc_gui.py`

### 2. 现代本地 Web 控制台 (免桌面权限 / 浏览器交互)
- **直接双击运行**：
  - 本目录下：双击 [`run_web.bat`](run_web.bat)（自动调用浏览器打开 `http://127.0.0.1:8989`）
  - 在总工程根目录下：双击 `启动_Web控制台.bat`
- **命令行启动**：
  - 本目录下：`python core/plc_web_gui.py`
  - 总工程目录下：`python 自动翻译与规范化工具_Workflow/core/plc_web_gui.py`

### 3. 独立免安装 EXE 绿色分发版 (无需 Python / 点击即用)
- 进入分发目录：[`dist/Corning_PLC_Toolkit_v2.0_Win64/`](dist/Corning_PLC_Toolkit_v2.0_Win64/)
- **直接双击运行**：`Corning_PLC_Toolkit.exe`（单文件 10.4MB，已内嵌 Python 核心与全部文档，可拷至任意电脑独立使用）
- 在总工程根目录下：亦可直接双击 `启动_独立免安装版EXE.bat`

### 4. CLI 命令行终端入口 (适合 CI/CD 与批处理)
微内核套件已支持**自动智能挂载**领域词典插件（修边机与意大利光伏边框专有词库），无需手动配置参数：

**如果在【自动翻译与规范化工具_Workflow】子目录下：**
```powershell
# 查看全局命令行帮助
python core/plc_table_toolkit.py --help

# 变量表批量处理示例 (策略 B: 锁定变量名，注释纯英文，自动加载插件)
python core/plc_table_toolkit.py vars --src-dir "..\康宁\3-修边机\io注释_备份_原始留档\变量表" --dst-dir "..\康宁\3-修边机\变量表" --mode B
```

**如果在【项目总根目录 PLC+HMI程序】下：**
```powershell
python 自动翻译与规范化工具_Workflow/core/plc_table_toolkit.py vars --src-dir "康宁\3-修边机\io注释_备份_原始留档\变量表" --dst-dir "康宁\3-修边机\变量表" --mode B
```

### 5. Python 原生 API 开发者入口
```python
from core.plc_table_toolkit import Kernel, VarTableProcessor, TableVerifier
```

---

## 二、 规范化工程目录结构 (Project Architecture)

经过全新分层治理，项目按照企业级软件规范清晰组织：

```text
自动翻译与规范化工具_Workflow/
│
├── 🚀 run_gui.bat                      <-- 【启动器】一键拉起桌面图形界面 (GUI)
├── 🌐 run_web.bat                      <-- 【启动器】一键拉起本地 Web 浏览器控制台
├── 📄 README.md                        <-- 【本项目总纲导航】
│
├── 📁 core/                            <-- 【核心业务与界面源码】
│   ├── plc_table_toolkit.py            <-- 微内核核心调度引擎、SPI 契约与统一 CLI 入口
│   ├── plc_gui.py                      <-- Windows 原生桌面 GUI 应用 (Tkinter/TTK)
│   └── plc_web_gui.py                  <-- 本地极简 Web 控制台 (内置 HTTP 服务)
│
├── 🔌 plugins/                         <-- 【领域扩展插件库】
│   ├── trimmer_dictionary_plugin.py    <-- 3-修边机专属机械与电气术语 SPI 插件
│   └── demo_custom_plugin.py           <-- 第三方插件开发官方示例源码
│
├── 📚 docs/                            <-- 【技术规范与文档中心】
│   ├── README_工作流使用说明.md         <-- 详尽使用手册 (43KB，全功能指南与 API 手册)
│   └── ARCHITECTURE_AND_EXTENSIBILITY.md <-- 架构白皮书 (54KB，4层微内核与兼容演进方案)
│
├── 🛠️ scripts/                         <-- 【工程构建与自动化管线】
│   ├── build_exe.py                    <-- PyInstaller 单文件独立 EXE 打包脚本
│   └── deliver_machine_3.py            <-- 3-修边机 12 个基准表全自动端到端交付流水线
│
├── 🧪 tests/                           <-- 【质量测试套件】
│   ├── test_e2e_toolkit.py             <-- 25 项端到端全量功能与极端边界测试套件 (Tier 1-4)
│   └── test_challenger_m1.py           <-- 对抗性压力测试套件
│
├── 📦 dist/                            <-- 【发布分发包目录】
│   └── Corning_PLC_Toolkit_v2.0_Win64/ <-- 绿色便携包 (含可执行程序与外置/内置双重文档)
│       └── Corning_PLC_Toolkit.exe
│
└── 🏛️ archive/                         <-- 【历史单体脚本归档】
    ├── plc_io_translator.py            <-- 早期 AutoShop IO 转换脚本
    ├── process_safety_relay_table.py   <-- 安全继电器专用表转换脚本
    ├── verify_all_8_var_tables.py      <-- 1-封边机早期质检脚本
    └── verify_safety_relay_table.py    <-- 安全继电器专用表质检脚本
```

---

## 三、 技术文档与核心参考

- 📖 **[《工作流详细使用说明手册》](docs/README_工作流使用说明.md)**：深入了解 CLI 详细参数、Python API 范例、第三方插件开发实战教程及全台位交付矩阵。
- 🏛️ **[《架构设计与扩展接入白皮书》](docs/ARCHITECTURE_AND_EXTENSIBILITY.md)**：深入了解微内核 4 层架构（解析/引擎/导出/质检）、UML 架构全景图、动态 SPI 生命周期及需求变更容错方案。
