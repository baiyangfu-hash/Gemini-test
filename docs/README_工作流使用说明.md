# 汇川 PLC 工业表格通用微内核套件与规范化工作流使用说明
## (Industrial PLC Table Microkernel Toolkit & Workflow User Manual)

> **版本**：v2.0.0 (Corning Enterprise Edition)  
> **适用项目**：美国康宁 (Corning Incorporated) CT173 项目 (1-封边机 / 2-撕胶带机 / 3-修边机)  
> **核心标准**：《IEC 61131-3 国际工控编程标准》、《电气术语定义标准与命名规范 (20251105-EN)》  
> **核心环境**：汇川 InoProShop (CODESYS V3.5 架构) / AutoShop / 汇川 PLC 全系列  

---

## 目录 (Table of Contents)

1. [套件概述与工业背景](#一-套件概述与工业背景)
2. [套件目录结构与文件职责](#二-套件目录结构与文件职责)
3. [核心功能特性与交付策略](#三-核心功能特性与交付策略)
4. [多维交互入口全景 (GUI / Web / CLI / API / SPI / EXE)](#四-多维交互入口全景-entry-points-overview)
   - [4.1 GUI 可视化桌面端操作指南 (core/plc_gui.py / run_gui.bat)](#41-gui-可视化桌面端操作指南-coreplc_guipy--run_guibat)
   - [4.2 Web REST API 微服务方案 (FastAPI 示例)](#42-web-rest-api-微服务方案-fastapi-示例)
5. [CLI 命令行接口全功能指南](#五-cli-命令行接口全功能指南)
   - [5.1 vars 子命令 (变量表批量处理与报告生成)](#51-vars-子命令-变量表批量处理与报告生成)
   - [5.2 io 子命令 (硬件 IO 注释表批量处理)](#52-io-子命令-硬件-io-注释表批量处理)
   - [5.3 verify 子命令 (自动化五重质量验收)](#53-verify-子命令-自动化五重质量验收)
   - [5.4 machine 子命令 (整机一键式交钥匙处理)](#54-machine-子命令-整机一键式交钥匙处理)
   - [5.5 插件扩展参数 (--plugin 与 --plugins-dir)](#55-插件扩展参数---plugin-与---plugins-dir)
6. [Python API 开发者指南](#六-python-api-开发者指南)
   - [6.1 顶层门面类 (Facade Classes)](#61-顶层门面类-facade-classes)
   - [6.2 微内核核心类与注册中心 (Kernel & PluginRegistry)](#62-微内核核心类与注册中心-kernel--pluginregistry)
   - [6.3 规范化内存数据模型 (TableDocument & TableRow)](#63-规范化内存数据模型-tabledocument--tablerow)
   - [6.4 SPI 插件扩展基类 (Service Provider Interfaces)](#64-spi-插件扩展基类-service-provider-interfaces)
   - [6.5 常用 Python 二次开发代码范例](#65-常用-python-二次开发代码范例)
7. [第三方扩展插件开发实战教程](#七-第三方扩展插件开发实战教程)
   - [7.1 为什么需要编写插件](#71-为什么需要编写插件)
   - [7.2 步骤 1：开发专有词典与动态正则插件 (DictionaryProviderPlugin)](#72-步骤-1开发专有词典与动态正则插件-dictionaryproviderplugin)
   - [7.3 步骤 2：开发后置质量验收断言插件 (PostVerifyRulePlugin)](#73-步骤-2开发后置质量验收断言插件-postverifyruleplugin)
   - [7.4 步骤 3：定义模块级注册钩子 (register_plugins)](#74-步骤-3定义模块级注册钩子-register_plugins)
   - [7.5 步骤 4：通过 CLI 或 Python API 加载插件](#75-步骤-4通过-cli-或-python-api-加载插件)
   - [7.6 官方示例脚本 demo_custom_plugin.py 源码精读](#76-官方示例脚本-demo_custom_pluginpy-源码精读)
8. [CT173 项目多机台交付追踪矩阵](#八-ct173-项目多机台交付追踪矩阵)
   - [8.1 全机台交付概览表](#81-全机台交付概览表)
   - [8.2 3-修边机 12 个基准变量表专项清单](#82-3-修边机-12-个基准变量表专项清单)
9. [工业级最佳实践与常见问题排查 (FAQ)](#九-工业级最佳实践与常见问题排查-faq)

---

## 一、 套件概述与工业背景

在高端装备国际化交付中，PLC 变量表与硬件 IO 注释的多语言标准化是美方（美国康宁 Corning Incorporated）严苛验收的关键指标。

**汇川 PLC 工业表格通用微内核套件 (`plc_table_toolkit.py`)** 专为汇川 InoProShop (CODESYS V3.5) 与 AutoShop 开发环境设计。套件全面升级为**4层微内核解耦架构**：
- **解析层 (Parser Layer)**：统一将多品牌、多格式工控表格转换为通用的 `TableDocument` 规范内存模型；
- **引擎层 (Engine Layer)**：5 阶段级联式工业电气术语翻译引擎（精确匹配、参数化正则、最长匹配贪婪替换、无注释智能推导、分隔符清洗），支持动态插件注入与优先级仲裁；
- **导出层 (Exporter Layer)**：严格保持工业级数据保真（GBK 编码、Windows CRLF 换行、9 列结构、尾随逗号、注释逗号转义）；
- **质检层 (Verifier Layer)**：行数一致性、CRLF 标记、9 列格式保真、变量名符号锁定、交付注释 0 中文残留等五重核心断言，并可串联第三方合规性校验插件。

本套件对外提供 **100% 向后兼容** 的 CLI 命令行接口与 Python API 门面，保证既有脚本、批处理管线（CI/CD）与自动化验收测试零侵入运行。

---

## 二、 套件目录结构与文件职责

```text
自动翻译与规范化工具_Workflow/
├── run_gui.bat                        <-- 【一键启动脚本】Windows 环境下启动可视化桌面端 (支持 Tkinter + 自动回退 Web 模式)
├── run_web.bat                        <-- 【网页启动脚本】在默认浏览器中打开可视化 Web 控制台 (http://127.0.0.1:8989)
├── run_translate_all.bat               <-- 【一键批处理】自动化执行整机变量表翻译与交付
├── README.md                          <-- 【全局总览】项目根目录统一导航与快速上手指南
├── core/                              <-- 【核心引擎模块】
│   ├── plc_table_toolkit.py           <-- 微内核核心、SPI 抽象接口、内置插件、兼容门面与 CLI 命令行入口
│   ├── plc_gui.py                     <-- 零依赖工业级桌面 GUI (Tkinter/TTK)，支持双重交付策略与五重质检
│   ├── plc_web_gui.py                 <-- 轻量级纯原生 Web 控制台服务 (基于 Python http.server)
│   └── __init__.py
├── plugins/                           <-- 【外部扩展插件目录】
│   ├── trimmer_dictionary_plugin.py   <-- 康宁 3-修边机专有电气与工艺术语 SPI 插件
│   ├── demo_custom_plugin.py          <-- 官方示范插件 (激光测距术语扩展 + 标签长度质检规则)
│   └── __init__.py
├── scripts/                           <-- 【生产与交付管线脚本】
│   ├── deliver_machine_3.py           <-- 康宁 3-修边机 12 张基准变量表端到端全自动交付与验证脚本
│   └── build_exe.py                   <-- 独立免安装 Windows 11 EXE 打包构建工具
├── dist/                              <-- 【绿色免安装分发包】
│   └── Corning_PLC_Toolkit_v2.0_Win64/
│       ├── Corning_PLC_Toolkit.exe    <-- 独立单文件可执行程序 (10.36 MB，内嵌运行时，无须安装 Python)
│       ├── 以浏览器Web模式启动.bat      <-- 浏览器模式快捷启动器
│       ├── README_工作流使用说明.md     <-- 用户操作手册
│       ├── ARCHITECTURE_AND_EXTENSIBILITY.md <-- 架构白皮书
│       └── plugins/                   <-- 外部插件放置目录
├── docs/                              <-- 【技术规范与架构文档】
│   ├── README_工作流使用说明.md         <-- 工作流使用说明书与开发手册 (本文件)
│   └── ARCHITECTURE_AND_EXTENSIBILITY.md <-- 微内核架构设计与扩展接入白皮书
├── tests/                             <-- 【自动化测试套件】
│   ├── test_e2e_toolkit.py            <-- 端到端全量功能与边界覆盖测试 (Tier 1-4，25 项测试 100% 通过)
│   └── test_challenger_m1.py          <-- 微内核与插件体系对抗性压力测试套件
└── archive/                           <-- 【历史工具留档归档】
    ├── plc_io_translator.py           <-- 历史 AutoShop IO 翻译脚本
    ├── process_safety_relay_table.py  <-- 历史安全继电器变量表处理脚本
    ├── verify_all_8_var_tables.py     <-- 历史 1-封边机 8 大变量表校验脚本
    └── verify_safety_relay_table.py   <-- 历史安全继电器变量表独立验收脚本
```

---

## 三、 核心功能特性与交付策略

### 1. 原生支持两种工控表格类型
- **全局变量表 (`*_变量表.csv`)**：针对 InoProShop / CODESYS 9 列标准结构（`序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,`），支持复杂结构体（DUT）、多维数组、定时器（TONR）、功能块（SV_Jog）等复杂工控符号解析。
- **IO 注释表 (`io注释-*.csv`)**：针对 AutoShop / InoProShop 物理软元件映射表（X, Y, M, D, R, B 等），智能适配首列地址、第 7 列或第 1 列注释的排版布局。

### 2. 双重交付策略方案 (Mode A / Mode B)
- **方案 B（推荐 / 康宁工程默认安全方案）**：
  - **变量名 100% 锁定不变**：彻底杜绝修改变量名导致梯形图、ST 代码、HMI 画面或外部通信地址关联失效；
  - **注释 100% 纯英文交付**：严格杜绝任何中文字符残留（0 Chinese Residue）；
  - **无注释变量智能推导**：若变量原有注释为空，但变量名本身为中文，智能提取变量名语义并推导补齐规范中文注释与纯英文注释。
- **方案 A（深度重构方案）**：
  - 变量名根据电气词典重构为标准工业英文缩写与蛇形下划线（snake_case）命名；
  - 适用于新建机台且梯形图尚未大规模绑定的全新开发场景。

### 3. 工业级数据保真机制
- **物理换行与编码安全**：严格使用 `GBK / CP936` 二进制编码与 Windows `\r\n` (CRLF) 物理换行，杜绝 Linux LF 导致的工控软件解析异常；
- **9 列与尾随逗号保真**：输出每一行严格保留 9 列字段并在行末补齐逗号（符合 InoProShop 原生导出规约）；
- **注释逗号防错位清洗**：针对注释中包含全角逗号 `，` 或半角逗号 `,` 的情况（如 `减速曲线类型：0，T型；1，S型`），系统在导出前自动将其清洗替换为 ` / `，杜绝 CSV 导入时列错位。

### 4. 单一交付总表与文首交互式目录
- 支持将整台机器的所有变量表自动聚合成一份完整的交付总表（如 `变量表中英文对照表_Corning交付版.md`）；
- 文首自带交互式章节导航（Table of Contents），支持按章节序号与文件名快速点击锚点跳转，文末配备“返回目录”链接。

---

## 四、 多维交互入口全景 (Entry Points Overview)

为了满足不同工程师角色与工业场景的接入需求，套件现已原生构建 **6 大标准化入口**：

| 入口类型 | 代表文件 / 形式 | 适用场景与对象 | 核心优势 |
| :--- | :--- | :--- | :--- |
| **1. 绿色免安装单文件 EXE** | [`dist/Corning_PLC_Toolkit_v2.0_Win64/Corning_PLC_Toolkit.exe`](file:///c:/Users/fubai/Documents/BaiduSyncdisk/项目/CT173-美国康宁-6月-付白杨/PLC+HMI程序/自动翻译与规范化工具_Workflow/dist/Corning_PLC_Toolkit_v2.0_Win64/Corning_PLC_Toolkit.exe) | 客户分发、无 Python 的现场 Win11 工控机 | **零依赖单文件** (10.36 MB)，内置 Python 运行时与完整文档，双击即用 |
| **2. 桌面 GUI 入口** | [`core/plc_gui.py`](file:///c:/Users/fubai/Documents/BaiduSyncdisk/项目/CT173-美国康宁-6月-付白杨/PLC+HMI程序/自动翻译与规范化工具_Workflow/core/plc_gui.py) / [`run_gui.bat`](file:///c:/Users/fubai/Documents/BaiduSyncdisk/项目/CT173-美国康宁-6月-付白杨/PLC+HMI程序/自动翻译与规范化工具_Workflow/run_gui.bat) | 现场电气工程师、调试人员、非编程用户 | **双重韧性** (优先 Tkinter 原生窗体，受限环境自动切 Web 控制台) |
| **3. Web 浏览器控制台** | [`core/plc_web_gui.py`](file:///c:/Users/fubai/Documents/BaiduSyncdisk/项目/CT173-美国康宁-6月-付白杨/PLC+HMI程序/自动翻译与规范化工具_Workflow/core/plc_web_gui.py) / [`run_web.bat`](file:///c:/Users/fubai/Documents/BaiduSyncdisk/项目/CT173-美国康宁-6月-付白杨/PLC+HMI程序/自动翻译与规范化工具_Workflow/run_web.bat) | 任意现代浏览器 (Edge / Chrome) 可视化操作 | 纯标准库 HTTP 服务 (端口 8989)，无需任何外部 Web 框架或依赖 |
| **4. CLI 命令行入口** | [`core/plc_table_toolkit.py`](file:///c:/Users/fubai/Documents/BaiduSyncdisk/项目/CT173-美国康宁-6月-付白杨/PLC+HMI程序/自动翻译与规范化工具_Workflow/core/plc_table_toolkit.py) | 自动化脚本、CI/CD 构建流水线、批处理运维 | 参数灵活、支持管道重定向、适合无人值守大批量生产 |
| **5. Python 原生 API** | `VarTableProcessor` / `TableVerifier` / `Kernel` | Python 开发者、二次开发应用、测试框架 | 内存对象级操作 (`TableDocument`)，可细粒度控制每个 AST 节点与过滤策略 |
| **6. SPI 插件扩展入口** | `BasePlugin` / `TableParserPlugin` 等 | 第三方生态开发者、新型工控格式适配 | 开放微内核契约，无需改动任何核心源码即可动态挂载新功能 |

---

### 4.1 GUI 可视化桌面端操作指南 (`core/plc_gui.py` / `run_gui.bat`)

#### 启动方式
- **方式一（推荐 / 双击一键启动）**：在项目根目录下直接双击运行 [`run_gui.bat`](file:///c:/Users/fubai/Documents/BaiduSyncdisk/项目/CT173-美国康宁-6月-付白杨/PLC+HMI程序/自动翻译与规范化工具_Workflow/run_gui.bat)；
- **方式二（浏览器模式启动）**：双击根目录下 [`run_web.bat`](file:///c:/Users/fubai/Documents/BaiduSyncdisk/项目/CT173-美国康宁-6月-付白杨/PLC+HMI程序/自动翻译与规范化工具_Workflow/run_web.bat)，自动在默认浏览器中打开控制台 (`http://127.0.0.1:8989`)；
- **方式三（独立单文件 EXE）**：进入 `dist/Corning_PLC_Toolkit_v2.0_Win64/` 直接双击 `Corning_PLC_Toolkit.exe`；
- **方式四（源码命令行启动）**：
  ```powershell
  python core/plc_gui.py
  ```

#### 界面六大功能面板
1. **📊 变量与工业文档只读对比检视器 (Variable & Document Inspector)**：
   - **PLC 品牌/平台下拉选单**：
     - `⚡ 自动智能识别 (Auto Detect)`：基于文件特征、工程扩展名与表头智能识别 AutoShop / InoProShop / GX Works3；
     - `汇川 AutoShop (H3U/H5U 小型PLC)`：专用于汇川小型 PLC 指令表/梯形图平台 (`.hcp`/`.hcpp`)，精确支持其 8 列硬件 IO 注释表（`序号,变量名,数据类型,数据值1~4,注释`）与 9 列 GVL 表；
     - `汇川 InoProShop (CODESYS/AM/AC 中大型PLC)`：专用于汇川中大型运动控制器 (基于 CODESYS V3.5 架构，`.project`)，严格维持 IEC 61131-3 规范的 9 列 CSV（带尾随逗号与保留列结构）；
     - `三菱 GX Works3 (iQ-R/iQ-F 平台)`：锁定三菱 GX Works3 27 列 TSV (伪 CSV) 与 2 列 IO 处理，保留 POU 块名并填入专属多语种列；
   - **目标交付语言下拉选单**：
     - `English (纯英文交付)`：输出纯英文规范注释（适用于康宁等项目）；
     - `Italiano (意大利语交付)`：输出意大利语规范注释（适用于意大利国家电网 Enel - 3Sun 等项目）；
   - **📁 外部机台浏览按钮**：允许用户点选任意磁盘路径的工控项目文件夹（包括外部三菱、西门子项目）；
   - **Side-by-Side 对齐展示**：清晰列出序号、变量名、数据类型（自动映射 IEC 61131-3 标准）、原始中文文档、交付外文文档以及状态标签（已翻译 / 智能推导 / 中文残留 / 未变更）；
   - **毫秒级模糊过滤**：支持按变量名、类型、中英文关键词即时过滤搜索；
   - **100% 纯只读安全承诺**：非排他流读取，不产生任何写入与文件锁冲突。
2. **📋 GVL 变量表批处理**：
   - 目录与单文件一键选择（支持联动自动推导输出目录）；
   - 策略 A / 策略 B 单选切换；
   - 联动平台与语种选单，自动选择正确的输出编码（GBK 或 UTF-16 LE）与列槽位；
   - 勾选是否生成规范中文留档 CSV 与整合 Markdown 总表；
   - 快捷按钮：一键打开交付文件夹、一键查看 Markdown 对照报告。
3. **🔌 IO 注释表转换**：
   - 选择源 IO 注释表与交付路径，全自动保留软元件地址、清洗分隔符并生成规范中文/英文/意文版本。
4. **✅ 质量验收门禁**：
   - 选定交付目录与原始留档目录，一键执行 5 重严苛工业质量校验，直观展示每个文件的 PASS / FAIL 状态。
5. **🏭 整机一键交付 (Turnkey Pipeline)**：
   - 选择机台主目录（内置 1-封边机 / 2-撕胶带机 / 3-修边机预设快捷按钮）；
   - 一键串联：扫描基准表 -> 策略 B 批量翻译 -> 规范中文留档 -> Markdown 单一总表导出 -> 全量质量门禁验收。
6. **🔍 工业术语沙盒测验**：
   - 提供工业注释与电气术语实时翻译输入框，即输即测；
   - 响应当前选定的目标语种（英文或意文）；
   - 内置常见高频工业词条快捷测试按钮（如 `PLCOpen状态机`、`修边刀上升到位`、`旋转角度：90°`、`温度设定：25℃` 等）。

#### 异步与安全特性
- **非阻塞多线程**：耗时任务在后台工作线程中执行，主窗口保持平滑响应不假死；
- **控制台彩色日志实时重定向**：底部黑色控制台实时流式输出执行详情，并通过绿色/红色标签高亮成功与告警项。

---

### 4.2 Web REST API 微服务方案 (FastAPI 示例)

若需要外部系统（如 C# WPF 工业上位机、MES 系统、浏览器 Web 端）通过网络调用表格处理能力，可使用轻量级 Web 服务封装（40 行代码即可启动）：

```python
# web_api_server.py (运行: uvicorn web_api_server:app --port 8000)
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response
import plc_table_toolkit as toolkit

app = FastAPI(title="Corning PLC Table Toolkit Web API")
kernel = toolkit.get_default_kernel()

@app.post("/api/v1/translate-text")
async def translate_text(text: str = Form(...)):
    """单条术语翻译接口"""
    engine = toolkit.IndustrialTermEngine(kernel=kernel)
    return {"source": text, "translated": engine.translate(text)}

@app.post("/api/v1/process-var-table")
async def process_var_table(file: UploadFile = File(...), mode: str = Form("B")):
    """单个 GVL 变量表 CSV 上传并返回纯英文交付 CSV"""
    content = await file.read()
    temp_in = f"/tmp/{file.filename}"
    temp_out = f"/tmp/en_{file.filename}"
    with open(temp_in, "wb") as f:
        f.write(content)

    proc = toolkit.VarTableProcessor(mode=mode, kernel=kernel)
    proc.process_file(temp_in, temp_out)

    with open(temp_out, "rb") as f:
        out_bytes = f.read()

    return Response(content=out_bytes, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=en_{file.filename}"})
```

---

## 五、 CLI 命令行接口全功能指南

微内核套件提供统一的命令行入口 `core/plc_table_toolkit.py`，支持 `vars`、`io`、`verify`、`machine` 四大核心子命令，并原生支持 `--plugin` 和 `--plugins-dir` 扩展参数。

```powershell
# 在项目根目录下查看全局帮助信息
python core/plc_table_toolkit.py --help
```

---

### 5.1 vars 子命令 (变量表批量处理与报告生成)

用于批量处理全局变量表 (GVL) 目录，生成 100% 纯英文交付 CSV、规范中文备份 CSV，并可选生成整合的 Markdown 对照总表。

#### 命令语法
```powershell
python core/plc_table_toolkit.py vars `
    --src-dir <源变量表目录> `
    --dst-dir <目标纯英文交付目录> `
    [--backup-cn <规范中文备份目录>] `
    [--mode {A,B}] `
    [--report <输出 Markdown 对照表路径>] `
    [--title <报告标题>] `
    [--plugin <外部插件路径.py>] `
    [--plugins-dir <插件目录>]
```

#### 参数说明
| 参数 | 类型 | 必须 | 默认值 | 描述 |
| :--- | :---: | :---: | :---: | :--- |
| `--src-dir` | string | 是 | - | 原始 GVL 变量表 CSV 所在目录 |
| `--dst-dir` | string | 是 | - | 处理后的纯英文交付 CSV 输出目录 |
| `--backup-cn` | string | 否 | None | 补齐推导注释后的规范中文备份 CSV 目录 |
| `--mode` | choice | 否 | `B` | 交付方案：`B` (推荐，保持变量名不变) 或 `A` (变量名英化) |
| `--report` | string | 否 | None | 生成的单一 Markdown 中英对照总表完整路径 |
| `--title` | string | 否 | `Corning Project Delivery` | 对照总表文首标题名称 |
| `--plugin` | string | 否 | - | 加载单个外部第三方插件文件 (可多次使用该参数指定多个文件) |
| `--plugins-dir` | string | 否 | None | 加载指定目录下的所有外部插件文件 (`.py`) |

#### 实战范例
```powershell
# 批量处理 3-修边机 变量表并挂载自定义传感器词典插件
python core/plc_table_toolkit.py vars `
    --src-dir "..\康宁\3-修边机\io注释_备份_原始留档\变量表" `
    --dst-dir "..\康宁\3-修边机\变量表" `
    --backup-cn "..\康宁\3-修边机\io注释_备份_规范中文版\变量表" `
    --mode B `
    --report "..\康宁\3-修边机\变量表\变量表中英文对照表_Corning交付版.md" `
    --title "Corning Project CT173 - 3-Trimmer Machine" `
    --plugin plugins/demo_custom_plugin.py
```

---

### 5.2 io 子命令 (硬件 IO 注释表批量处理)

用于批量处理硬件物理软元件 IO 注释映射表，生成纯英文交付版本与规范中文备份。

#### 命令语法
```powershell
python core/plc_table_toolkit.py io `
    --src-dir <源 IO 注释表目录> `
    --dst-dir <目标交付目录> `
    [--backup-cn <规范中文备份目录>] `
    [--plugin <外部插件路径.py>] `
    [--plugins-dir <插件目录>]
```

#### 参数说明
| 参数 | 类型 | 必须 | 默认值 | 描述 |
| :--- | :---: | :---: | :---: | :--- |
| `--src-dir` | string | 是 | - | 原始 IO 注释 CSV 所在目录 |
| `--dst-dir` | string | 是 | - | 纯英文交付 IO 注释 CSV 输出目录 |
| `--backup-cn` | string | 否 | None | 规范中文备份输出目录 |
| `--plugin` | string | 否 | - | 加载外部第三方插件文件 |
| `--plugins-dir` | string | 否 | None | 加载指定目录下的全部插件文件 |

#### 实战范例
```powershell
# 批量处理 2-撕胶带机 的 IO 注释表
python core/plc_table_toolkit.py io `
    --src-dir "..\康宁\2-撕胶带机\io注释_备份_原始留档" `
    --dst-dir "..\康宁\2-撕胶带机\io注释" `
    --backup-cn "..\康宁\2-撕胶带机\io注释_备份_规范中文版"
```

---

### 5.3 verify 子命令 (自动化五重质量验收)

用于对交付目录执行全量、无死角的自动化质检验收。若所有文件合格，进程返回退出码 `0`；一旦有任何文件违背断言，控制台输出具体行号与违规项，并返回退出码 `1`（极利于集成至 Jenkins / GitHub Actions 等 CI/CD 质量门禁）。

#### 命令语法
```powershell
python core/plc_table_toolkit.py verify `
    --src <原始留档基准目录> `
    --target <待质检验收交付目录> `
    [--type {var,io}] `
    [--mode {A,B}] `
    [--plugin <外部插件路径.py>] `
    [--plugins-dir <插件目录>]
```

#### 核心五重断言与插件断言
1. **行数严格一致性断言**：交付文件物理行数必须与原始留档 1:1 吻合；
2. **Windows CRLF 换行断言**：文件二进制流必须包含 `\r\n` 物理换行符；
3. **9 列结构保真断言**：每行逗号拆分字段数必须不小于 9 列，且尾随逗号结构完整；
4. **方案 B 变量名锁定断言**：原始变量名与交付变量名必须字符级绝对一致；
5. **注释列 0 中文残留断言**：交付注释列严禁包含任何 CJK 统一汉字 (`[\u4e00-\u9fff]`)；
6. **插件扩展后置断言**：自动触发所有已注册 `PostVerifyRulePlugin`（如标签长度、特定保留字等）。

#### 实战范例
```powershell
# 对 3-修边机 变量表交付成果执行五重质检及自定义合规规则校验
python core/plc_table_toolkit.py verify `
    --src "..\康宁\3-修边机\io注释_备份_原始留档\变量表" `
    --target "..\康宁\3-修边机\变量表" `
    --type var `
    --mode B `
    --plugin plugins/demo_custom_plugin.py
```
*控制台输出示意：*
```text
================ 启动自动化质量验收 (..\康宁\3-修边机\变量表) ================
[PASS] 产量_变量表.csv          | 校验项全部通过 (行数吻合 / CRLF / 9列保真 / 0中文残留)
[PASS] 伺服_变量表.csv          | 校验项全部通过 (行数吻合 / CRLF / 9列保真 / 0中文残留)
...
[PASS] 配方_变量表.csv          | 校验项全部通过 (行数吻合 / CRLF / 9列保真 / 0中文残留)
-----------------------------------------------------------------
FINAL RESULT: ALL 12 FILES PASSED 100% QUALITY CHECKS!
```

---

### 5.4 machine 子命令 (整机一键式交钥匙处理)

针对康宁标准机台目录布局的一键式交钥匙处理工具。自动识别内部的 `io注释_备份_原始留档/变量表` 目录，全自动生成交付纯英文版、规范中文版、对照总表并立即执行自动化五重验收。

#### 命令语法
```powershell
python core/plc_table_toolkit.py machine `
    --machine-dir <机台根目录> `
    [--mode {A,B}] `
    [--plugin <外部插件路径.py>] `
    [--plugins-dir <插件目录>]
```

#### 实战范例
```powershell
# 一键完成 3-修边机 全套交付处理与质量验收
python core/plc_table_toolkit.py machine --machine-dir "..\康宁\3-修边机" --mode B
```

---

### 5.5 插件扩展参数 (--plugin 与 --plugins-dir)

微内核支持在任意子命令或顶层解析器中无缝传递插件：
- **指定单个或多个插件**：
  ```powershell
  python core/plc_table_toolkit.py vars ... --plugin plugins/demo_custom_plugin.py
  ```
- **指定插件目录 (批量扫描)**：
  ```powershell
  python core/plc_table_toolkit.py vars ... --plugins-dir "plugins"
  ```

---

## 六、 Python API 开发者指南

### 6.1 顶层门面类 (Facade Classes)

为了保障历史系统与自动化测试脚本的 100% 向后兼容性，`plc_table_toolkit` 在顶层命名空间暴露了四大经典门面类：

```python
from plc_table_toolkit import (
    VarTableProcessor, 
    IOTableProcessor, 
    IndustrialTermEngine, 
    TableVerifier
)
```

#### 1. IndustrialTermEngine (术语与翻译引擎门面)
```python
class IndustrialTermEngine:
    def __init__(self, custom_dict: Optional[Dict[str, str]] = None, kernel: Optional[Kernel] = None):
        """
        :param custom_dict: 用户临时专有词典映射 {中文: 英文}，拥有最高覆盖仲裁权
        :param kernel: 底层绑定的微内核实例 (缺省时使用全局默认内核)
        """
        ...

    def translate(self, text: str) -> str:
        """核心翻译方法：输入中文或混合文本，返回 100% 纯英文"""
        ...

    def derive_chinese_comment(self, var_name: str, existing_comment: str) -> str:
        """根据变量名智能推导补齐中文注释"""
        ...
```

#### 2. VarTableProcessor (GVL 全局变量表处理器门面)
```python
class VarTableProcessor:
    def __init__(self, mode: str = "B", term_engine: Optional[IndustrialTermEngine] = None, kernel: Optional[Kernel] = None):
        """
        :param mode: 交付模式 'B' (默认，保持变量名不变) 或 'A' (变量名英化)
        """
        ...

    def process_file(self, src_path: str, dst_en_path: str, dst_cn_path: Optional[str] = None) -> List[Tuple]:
        """
        处理单个 GVL 变量表 CSV 文件
        :return: 逐行变更记录 5 元组列表 [(序号, 变量名, 类型, 规范中文注释, 交付英文注释), ...]
        """
        ...

    def process_directory(self, src_dir: str, dst_en_dir: str, dst_cn_dir: Optional[str] = None,
                          report_md_path: Optional[str] = None, project_title: str = "Corning Delivery") -> Dict[str, List[Tuple]]:
        """批量处理整个变量表目录，返回 {文件名: 记录列表}"""
        ...

    def generate_markdown_report(self, all_records: Dict[str, List[Tuple]], report_path: str,
                                 project_title: str = "Corning Project CT173") -> None:
        """生成带交互式 Table of Contents 与锚点跳转的交付总表"""
        ...
```

#### 3. IOTableProcessor (IO 注释表处理器门面)
```python
class IOTableProcessor:
    def __init__(self, term_engine: Optional[IndustrialTermEngine] = None, kernel: Optional[Kernel] = None):
        ...

    def process_file(self, src_path: str, dst_en_path: str, dst_cn_path: Optional[str] = None) -> List[Tuple]:
        """
        处理单个 IO 注释 CSV 文件
        :return: 记录 3 元组列表 [(软元件地址, 原始注释, 纯英文注释), ...]
        """
        ...
```

#### 4. TableVerifier (自动化质量验收门面)
```python
class TableVerifier:
    @staticmethod
    def verify_file(src_path: str, target_path: str, mode: str = "B", is_var_table: bool = True,
                    kernel: Optional[Kernel] = None) -> Tuple[bool, List[str]]:
        """单文件质量验收：返回 (是否通过, 错误信息列表)"""
        ...

    @classmethod
    def verify_directory(cls, src_dir: str, target_dir: str, mode: str = "B", is_var_table: bool = True,
                         kernel: Optional[Kernel] = None) -> bool:
        """目录级批量自动化质量验收：控制台输出诊断日志，返回布尔值"""
        ...
```

---

### 6.2 微内核核心类与注册中心 (Kernel & PluginRegistry)

对于需要深入控制管道生命周期、动态插拔插件的高级开发者，可以直接操作 `Kernel` 对象：

```python
from plc_table_toolkit import Kernel, get_default_kernel

# 获取全局默认微内核实例，或实例化全新独立内核
kernel = Kernel()

# 1. 动态装载外部插件
kernel.load_plugin_file("my_plugin.py")
kernel.load_plugins_dir("./plugins")

# 2. 注册已实例化的插件对象
kernel.register_plugin(my_custom_plugin)

# 3. 解析文件为规范内存对象
doc = kernel.parse("alarm_table.csv", encoding="gbk")

# 4. 执行多阶段翻译
en_text = kernel.translate_text("修边刀使用统计")

# 5. 序列化导出
kernel.export(doc, "output.csv", format_name="gvl_csv", mode="B")

# 6. 执行全量质检 (五重断言 + 插件后置规则)
passed, errors = kernel.verify("src.csv", "dst.csv", mode="B", is_var_table=True)
```

---

### 6.3 规范化内存数据模型 (TableDocument & TableRow)

微内核定义了统一的强类型内存数据实体：

```python
@dataclass
class TableRow:
    no: str = ""                         # 序号 (Col 0)
    name: str = ""                       # 变量名 / 软元件地址 (Col 1 或 Col 0)
    data_type: str = ""                  # 数据类型 (Col 2，如 BOOL, DINT, TONR)
    init_hide: str = ""                  # 隐藏初始值 (Col 3)
    init_val: str = ""                   # 初始值 (Col 4)
    retain: str = ""                     # 掉电保持 (Col 5)
    publish: str = ""                    # 网络公开 (Col 6)
    comment: str = ""                    # 原始注释 (Col 7 或 Col 1)
    addr: str = ""                       # 软元件地址 / 附加列 (Col 8)
    raw_parts: List[str] = field(...)    # 原始 CSV 切片 token
    raw_line: str = ""                   # 原始物理行文本 (完全保真)
    extra: Dict[str, Any] = field(...)   # 运行时动态扩展属性 (存放 new_en_c, new_cn_c 等)

@dataclass
class TableDocument:
    file_path: str = ""                  # 源文件绝对或相对路径
    table_type: str = "var"              # 'var' (GVL 变量表) 或 'io' (IO 注释表)
    headers: List[str] = field(...)      # 列头名称数组
    rows: List[TableRow] = field(...)    # 行记录列表
    metadata: Dict[str, Any] = field(...)# 元数据字典 (encoding, line_count 等)
    raw_lines: List[str] = field(...)    # 原始行字符串列表
```

---

### 6.4 SPI 插件扩展基类 (Service Provider Interfaces)

开发者通过继承以下抽象基类实现功能扩展：

```python
from plc_table_toolkit import (
    BasePlugin,
    TableParserPlugin,
    DictionaryProviderPlugin,
    TableExporterPlugin,
    PostVerifyRulePlugin
)
```

- **`BasePlugin`**：所有插件的基础父类，提供 `on_load(kernel)`, `initialize(config)`, `on_unload()` 生命周期钩子与 `priority` 优先级属性。
- **`TableParserPlugin`**：实现 `can_parse(file_path, raw_bytes)` 与 `parse(file_path, encoding)`。
- **`DictionaryProviderPlugin`**：实现 `get_exact_phrases()`, `get_word_pairs()`, `get_regex_rules()`。
- **`TableExporterPlugin`**：实现 `can_export(format_name)` 与 `export(doc, output_path, **kwargs)`。
- **`PostVerifyRulePlugin`**：实现 `verify(src_path, tgt_path, doc, context) -> Tuple[bool, List[str]]`。

---

### 6.5 常用 Python 二次开发代码范例

#### 范例 1：使用自定义字典进行文件处理
```python
from plc_table_toolkit import IndustrialTermEngine, VarTableProcessor

# 定义项目专有词典
my_custom_terms = {
    "超声波清洗启闭": "Ultrasonic Cleaning Enable / Disable",
    "吸盘真空破除": "Suction Cup Vacuum Break",
}

# 实例化引擎与处理器
engine = IndustrialTermEngine(custom_dict=my_custom_terms)
processor = VarTableProcessor(mode="B", term_engine=engine)

# 处理单个文件
records = processor.process_file(
    src_path=r"..\io注释_备份_原始留档\变量表\准备_变量表.csv",
    dst_en_path=r"..\变量表\准备_变量表.csv",
    dst_cn_path=r"..\io注释_备份_规范中文版\变量表\准备_变量表.csv"
)
print(f"处理完成，共转换 {len(records)} 行数据！")
```

#### 范例 2：完整目录批量处理与自动化质检流水线
```python
from plc_table_toolkit import VarTableProcessor, TableVerifier

src_dir = r"C:\Corning\3-Trimmer\io注释_备份_原始留档\变量表"
dst_en_dir = r"C:\Corning\3-Trimmer\变量表"
dst_cn_dir = r"C:\Corning\3-Trimmer\io注释_备份_规范中文版\变量表"
report_path = r"C:\Corning\3-Trimmer\变量表\变量表中英文对照表_Corning交付版.md"

# 1. 批量转换并生成交付总表
proc = VarTableProcessor(mode="B")
all_records = proc.process_directory(
    src_dir=src_dir,
    dst_en_dir=dst_en_dir,
    dst_cn_dir=dst_cn_dir,
    report_md_path=report_path,
    project_title="Corning CT173 3-Trimmer Machine"
)

# 2. 自动化质量门禁验收
passed = TableVerifier.verify_directory(
    src_dir=src_dir,
    target_dir=dst_en_dir,
    mode="B",
    is_var_table=True
)

if not passed:
    raise RuntimeError("CI/CD 验收断言失败，拒绝合入构建！")
print("自动化验收 100% 通过，准予交付！")
```

---

## 七、 第三方扩展插件开发实战教程

### 7.1 为什么需要编写插件

在多工厂、多机台的工业交付中，不同工艺段的专业词汇（如修边刀、撕胶带、点胶阀、激光位移计）各不相同，且各客户（如康宁、京东方、宁德时代）对 HMI 标签长度、命名规则有差异化标准。

通过编写独立的 SPI 插件：
1. **核心零修改 (Zero Core Modification)**：无需触碰核心工具库代码，防止代码分叉；
2. **热插拔与隔离 (Hot-Plugging & Isolation)**：插件按优先级动态加载，项目结束后可直接移除；
3. **复用与发布 (Reusable Assets)**：专有硬件厂商（如基恩士传感器、SMC 阀岛）可将自身词库打包为插件对外交付。

---

### 7.2 步骤 1：开发专有词典与动态正则插件 (DictionaryProviderPlugin)

创建一个 Python 脚本（如 `my_custom_plugin.py`），继承 `DictionaryProviderPlugin`：

```python
import re
from typing import Dict, List, Tuple, Callable, Union
from plc_table_toolkit import DictionaryProviderPlugin

class MyTrimmerDictionaryPlugin(DictionaryProviderPlugin):
    plugin_id = "my_trimmer_dictionary"
    plugin_name = "My Trimmer Domain Dictionary Provider"
    version = "1.0.0"
    priority = 20  # 优先级数值越小越优，20 优于内置词库的 100

    def get_exact_phrases(self) -> Dict[str, str]:
        """精确全词匹配 (优先命中)"""
        return {
            "修边刀使用统计": "Trimming Cutter Usage Statistics",
            "削边深度微调": "Trimming Depth Fine Tuning",
            "激光测距位移传感器通讯异常": "Laser Distance Displacement Sensor Comm Error!",
        }

    def get_word_pairs(self) -> List[Tuple[str, str]]:
        """多词素贪婪子串替换对"""
        return [
            ("激光测距传感器", "Laser Distance Sensor"),
            ("修边刀伺服", "Trimming Cutter Servo"),
            ("修边刀", "Trimming Cutter"),
            ("削边刀", "Trimming Cutter"),
            ("位移计", "Displacement Gauge"),
        ]

    def get_regex_rules(self) -> List[Tuple[Union[re.Pattern, str], Callable]]:
        """动态参数化正则规则"""
        def handle_sensor(m: re.Match, tr: Callable[[str], str]) -> str:
            sid = m.group(1)
            raw_st = m.group(2)
            st_map = {"正常": "Normal", "异常": "Error!", "报警": "Alarm!"}
            return f"Laser Sensor #{sid} {st_map.get(raw_st, tr(raw_st))}"

        return [
            (re.compile(r'^激光传感器(\d+)#?(正常|异常|报警)$'), handle_sensor),
        ]
```

---

### 7.3 步骤 2：开发后置质量验收断言插件 (PostVerifyRulePlugin)

继承 `PostVerifyRulePlugin`，添加项目专有的质量校验断言：

```python
from typing import Dict, List, Tuple, Any
from plc_table_toolkit import PostVerifyRulePlugin, TableDocument

class MyComplianceRulePlugin(PostVerifyRulePlugin):
    plugin_id = "my_compliance_verifier"
    plugin_name = "HMI Tag Length & Formatting Rule"
    version = "1.0.0"
    priority = 10

    def __init__(self, max_len: int = 120):
        super().__init__()
        self.max_len = max_len

    def verify(self, src_path: str, tgt_path: str, doc: TableDocument, context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        for idx, row in enumerate(doc.rows, 1):
            if not row.raw_line.strip() or len(row.raw_parts) < 8:
                continue

            comment = row.comment

            # 规则 1: 英文注释不得超出 HMI 字符限制
            if len(comment) > self.max_len:
                errors.append(f"第 {idx} 行注释长度超标 ({len(comment)} > {self.max_len}): '{comment}'")

            # 规则 2: 英文交付注释内严禁残留未转义的半角逗号
            if ',' in comment:
                errors.append(f"第 {idx} 行注释含有未转义半角逗号: '{comment}'")

        return (len(errors) == 0), errors
```

---

### 7.4 步骤 3：定义模块级注册钩子 (register_plugins)

在插件脚本末尾提供入口函数 `register_plugins`，使 CLI 的 `--plugin` 参数能够自动加载：

```python
from plc_table_toolkit import Kernel, BasePlugin

def register_plugins(kernel: Kernel) -> List[BasePlugin]:
    """供 --plugin 自动调用的注册入口"""
    p1 = MyTrimmerDictionaryPlugin()
    p2 = MyComplianceRulePlugin(max_len=120)
    kernel.register_plugin(p1)
    kernel.register_plugin(p2)
    return [p1, p2]
```

---

### 7.5 步骤 4：通过 CLI 或 Python API 加载插件

#### 通过 CLI 运行
```powershell
python core/plc_table_toolkit.py vars `
    --src-dir "..\变量表_原始" `
    --dst-dir "..\变量表_交付" `
    --plugin my_custom_plugin.py
```

#### 通过 Python API 加载
```python
from plc_table_toolkit import Kernel, VarTableProcessor

kernel = Kernel()
# 动态加载并注册外部插件文件
kernel.load_plugin_file("my_custom_plugin.py")

processor = VarTableProcessor(mode="B", kernel=kernel)
processor.process_directory("..\变量表_原始", "..\变量表_交付")
```

---

### 7.6 官方示例脚本 plugins/demo_custom_plugin.py 源码精读

工作流目录内自带可独立执行的完整范例 `plugins/demo_custom_plugin.py`。该脚本演示了从插件定义、微内核注入、内存测试数据生成、全流程转换到五重质检验收的完整闭环。

执行命令进行运行验证：
```powershell
python plugins/demo_custom_plugin.py
```
*控制台输出结果：*
```text
======================================================================
 [DEMO] 第三方扩展插件 SPI 动态注入与质量验收测试
======================================================================
[*] 已注册词库插件: [laser_sensor_trimmer_dictionary] (优先级: 20)
[*] 已注册质检插件: [corning_compliance_verifier] (优先级: 10)

--- 1. 词典插件动态翻译验证 ---
  中文: 激光测距位移传感器通讯异常   -> 英文: Laser Distance Displacement Sensor Comm Error!
  中文: 激光测距传感器1#报警         -> 英文: Laser Distance Sensor #1 Alarm!
  中文: 修边刀使用统计               -> 英文: Trimming Cutter Usage Statistics
  中文: 削边深度微调                 -> 英文: Trimming Depth Fine Tuning

--- 2. 表格批量转换与生成 ---
  -> 处理完成，转换记录数: 4 行

--- 3. 5 重核心断言 + 插件自定义规则自动化质检 ---
  [PASS] 5 重核心检测 (行数/CRLF/9列/变量名/0中文) 全部通过！
  [PASS] 自定义插件规则 [CorningComplianceRulePlugin] 校验通过！

======================================================================
 [PASS] DEMO CUSTOM PLUGIN DYNAMIC REGISTRATION & VERIFICATION PASSED!
======================================================================
```

---

## 八、 CT173 项目多机台交付追踪矩阵

### 8.1 全机台交付概览表

美国康宁 (Corning Incorporated) CT173 项目涵盖三大自动化核心工艺机台，全部表格已完成微内核规范化处理与全量质量验收：

| 机台序号 | 设备名称 | 模块分类 | 表格数量 | 数据行数 | 自动化验收状态 | 交付总表归档路径 |
| :---: | :--- | :--- | :---: | :---: | :---: | :--- |
| **01** | **1-封边机** | 硬件 IO 注释表 | 7 个 CSV | 832 行 | **100% PASS** | `1-封边机\io注释英文对照表_Corning交付版.md` |
| **01** | **1-封边机** | 全局变量表 (GVL) | 8 个 CSV | 8,284 行 | **100% PASS** | `1-封边机\变量表\变量表中英文对照表_Corning交付版.md` |
| **02** | **2-撕胶带机** | 硬件 IO 注释表 | 7 个 CSV | 948 行 | **100% PASS** | `2-撕胶带机\io注释英文对照表_Corning交付版.md` |
| **02** | **2-撕胶带机** | 全局变量表 (GVL) | 12 个 CSV | 19,811 行 | **100% PASS** | `2-撕胶带机\变量表\变量表中英文对照表_Corning交付版.md` |
| **03** | **3-修边机** | 全局变量表 (GVL) | 12 个 CSV | 15,714 行 | **100% PASS** | `3-修边机\变量表\变量表中英文对照表_Corning交付版.md` |
| **汇总** | **全线三台核心装备** | **全量工程表格** | **46 个表格** | **45,589 行** | **零缺陷交付** | 均配备文首交互式目录与锚点跳转导航 |

---

### 8.2 3-修边机 12 个基准变量表专项清单

3-修边机是本阶段核心交付机台，包含 12 个关键工艺全局变量表（严格排除临时留档 `_new` 后缀文件）：

| 序号 | 变量表基准文件名 | 原始行数 | 数据行数 | 核心工控工艺涉及范围 | 纯英文交付路径 | 规范中文备份路径 |
| :---: | :--- | :---: | :---: | :--- | :--- | :--- |
| 1 | `产量_变量表.csv` | 134 行 | 133 行 | 班次产量、总产量统计、节拍计算 | `3-修边机\变量表\` | `3-修边机\io注释_备份_规范中文版\变量表\` |
| 2 | `伺服_变量表.csv` | 382 行 | 381 行 | 修边刀进给轴、定位轴伺服控制 | `3-修边机\变量表\` | `3-修边机\io注释_备份_规范中文版\变量表\` |
| 3 | `修边刀使用统计_变量表.csv` | 13 行 | 12 行 | 刀具寿命、修边刀磨损与更换预警 | `3-修边机\变量表\` | `3-修边机\io注释_备份_规范中文版\变量表\` |
| 4 | `停机_变量表.csv` | 35 行 | 34 行 | 正常停机、急停、工艺联锁互锁 | `3-修边机\变量表\` | `3-修边机\io注释_备份_规范中文版\变量表\` |
| 5 | `准备_变量表.csv` | 1,455 行 | 1,454 行 | 气缸初态、安全继电器、工位就绪 | `3-修边机\变量表\` | `3-修边机\io注释_备份_规范中文版\变量表\` |
| 6 | `回原点_变量表.csv` | 313 行 | 312 行 | 多轴机械回原点、回原点状态字 | `3-修边机\变量表\` | `3-修边机\io注释_备份_规范中文版\变量表\` |
| 7 | `手动操作_变量表.csv` | 46 行 | 45 行 | HMI 手动点动、吸盘控制、阀体调试 | `3-修边机\变量表\` | `3-修边机\io注释_备份_规范中文版\变量表\` |
| 8 | `报警_变量表.csv` | 913 行 | 912 行 | 故障代码 (F代码)、安全门报警 | `3-修边机\变量表\` | `3-修边机\io注释_备份_规范中文版\变量表\` |
| 9 | `系统准备_变量表.csv` | 45 行 | 44 行 | 系统级上电自检、主回路使能 | `3-修边机\变量表\` | `3-修边机\io注释_备份_规范中文版\变量表\` |
| 10 | `自动_变量表.csv` | 11,570 行 | 11,569 行 | 主控自动节拍逻辑、连续轨迹运行 | `3-修边机\变量表\` | `3-修边机\io注释_备份_规范中文版\变量表\` |
| 11 | `输送归正_变量表.csv` | 108 行 | 107 行 | 输送线伺服、四角吸盘对齐修正 | `3-修边机\变量表\` | `3-修边机\io注释_备份_规范中文版\变量表\` |
| 12 | `配方_变量表.csv` | 700 行 | 699 行 | 玻璃规格配方、工艺参数下载 | `3-修边机\变量表\` | `3-修边机\io注释_备份_规范中文版\变量表\` |
| **总计** | **全部 12 个基准变量表** | **15,714 行** | **15,702 行** | **五重断言 100% 验收通过，0 中文残留** | 交付总表：`变量表中英文对照表_Corning交付版.md` |

---

## 九、 工业级最佳实践与常见问题排查 (FAQ)

### Q1: 汇川 InoProShop 导入 CSV 报“列数不匹配”或“格式错误”怎么办？
- **原因 1（换行符）**：文件被 Git 自动转换为 Linux LF (`\n`)。汇川 PLC 强制要求 Windows CRLF (`\r\n`)。
  - *解决*：使用套件内置 Exporter 导出，强制保证二进制 CRLF。
- **原因 2（逗号未清洗）**：注释中手动输入了半角逗号 `,`，导致 CSV 被错误分列为 10 列以上。
  - *解决*：套件已内置逗号自动清洗功能（将 `,` 和 `，` 统一替换为 ` / `）。

### Q2: 遇到少量生僻专业词汇翻译不精准，如何优雅扩充词库？
- **推荐做法**：切勿直接修改 `plc_table_toolkit.py` 源码。
- **扩展方式**：编写一个继承 `DictionaryProviderPlugin` 的自定义插件（设置 `priority = 10`），或在调用 Python API 时传入 `custom_dict={"生僻词": "Standard Term"}`。高优先级插件会自动在微内核启动时覆盖内置词条。

### Q3: 执行 verify 质检报告提示“注释列包含中文字符”如何排查？
- 控制台会打印出具体违规的文件名、行号与未翻译汉字，例如：
  `[FAIL] 报警_变量表.csv | 发现异常: 第 124 行注释列包含中文字符 [刀]: (F31) 削边刀异常`
- 开发者只需将违规词汇（如“削边刀”）补充进项目词典插件即可。

### Q4: 为什么方案 B 是工控交付的“黄金准则”？
- 工控 PLC 梯形图、功能块、结构化文本（ST）以及 HMI 触摸屏画面通常使用变量名进行物理符号寻址绑定。如果直接修改变量名，可能引发数百处逻辑关联断开；方案 B 严格锁定变量名不变，仅将说明注释翻译为纯英文并规范化，实现了“**逻辑零风险、交付高标准**”的工业质量目标。

---

*版权所有 © 2026 美国康宁 CT173 项目组 & 自动化交付质量保证组。*
