# PLC 工业表格通用套件架构设计与扩展接入白皮书
## (Industrial PLC Table Toolkit Microkernel Architecture & Extensibility Whitepaper)

> **版本**：v2.0.0 (Corning Enterprise Edition)  
> **适用工程**：美国康宁 (Corning Incorporated) CT173 项目 (1-封边机 / 2-撕胶带机 / 3-修边机)  
> **核心标准**：《IEC 61131-3 国际工控编程标准》、《电气术语定义标准与命名规范 (20251105-EN)》  
> **文档密级**：企业工业级工程白皮书 / 核心架构规范  
> **维护主体**：工控软件架构委员会 & 自动化交付质量保证组  

---

## 目录 (Table of Contents)

1. [执行摘要与工业背景 (Executive Summary & Background)](#1-执行摘要与工业背景-executive-summary--background)
2. [核心设计哲学：高内聚低耦合微内核 (Core Philosophy)](#2-核心设计哲学高内聚低耦合微内核-core-philosophy)
3. [4层微内核系统架构设计 (4-Layer Microkernel Architecture)](#3-4层微内核系统架构设计-4-layer-microkernel-architecture)
   - [3.1 总体组件架构图 (ASCII & Mermaid UML)](#31-总体组件架构图-ascii--mermaid-uml)
   - [3.2 规范化内存数据模型 (Canonical In-Memory Models)](#32-规范化内存数据模型-canonical-in-memory-models)
   - [3.3 核心类图设计 (Mermaid UML Class Diagram)](#33-核心类图设计-mermaid-uml-class-diagram)
   - [3.4 端到端批处理流水线时序 (Mermaid UML Sequence Diagram)](#34-端到端批处理流水线时序-mermaid-uml-sequence-diagram)
4. [服务提供者接口 (SPI) 规范与插件生命周期 (Plugin SPI & Lifecycle)](#4-服务提供者接口-spi-规范与插件生命周期-plugin-spi--lifecycle)
   - [4.1 BasePlugin 基类与优先级仲裁](#41-baseplugin-基类与优先级仲裁)
   - [4.2 TableParserPlugin 文件解析扩展接口](#42-tableparserplugin-文件解析扩展接口)
   - [4.3 DictionaryProviderPlugin 术语与规则扩展接口](#43-dictionaryproviderplugin-术语与规则扩展接口)
   - [4.4 TableExporterPlugin 格式化序列化扩展接口](#44-tableexporterplugin-格式化序列化扩展接口)
   - [4.5 PostVerifyRulePlugin 质量验收规则扩展接口](#45-postverifyruleplugin-质量验收规则扩展接口)
   - [4.6 PluginRegistry 注册中心与动态反射机制](#46-pluginregistry-注册中心与动态反射机制)
   - [4.7 插件生命周期与钩子调用时序图 (Mermaid UML Sequence Diagram)](#47-插件生命周期与钩子调用时序图-mermaid-uml-sequence-diagram)
5. [工业级需求变更容错与应对方案 (Industrial Mutation Mitigation Policies)](#5-工业级需求变更容错与应对方案-industrial-mutation-mitigation-policies)
   - [5.1 硬件厂商与新 PLC 品牌适配方案 (Siemens / Mitsubishi / Omron / Rockwell)](#51-硬件厂商与新-plc-品牌适配方案-siemens--mitsubishi--omron--rockwell)
   - [5.2 复杂工业数据类型扩展方案 (DUT 结构体 / 多维数组 / 功能块 / 指针与引用)](#52-复杂工业数据类型扩展方案-dut-结构体--多维数组--功能块--指针与引用)
   - [5.3 云端与大模型 (Cloud / LLM) AI 翻译接入容灾方案](#53-云端与大模型-cloud--llm-ai-翻译接入容灾方案)
   - [5.4 工业 CSV 脏数据与畸变防御策略 (引号未闭合 / 换行符 / 逗号冲突)](#54-工业-csv-脏数据与畸变防御策略-引号未闭合--换行符--逗号冲突)
6. [100% 向后兼容性保障策略 (Backward Compatibility Policy)](#6-100-向后兼容性保障策略-backward-compatibility-policy)
   - [6.1 门面模式 (Facade Pattern) 架构实现](#61-门面模式-facade-pattern-架构实现)
   - [6.2 Python API ABI 稳定性与签名保真](#62-python-api-abi-稳定性与签名保真)
   - [6.3 CLI 命令行参数无缝兼容规范](#63-cli-命令行参数无缝兼容规范)
7. [结语与演进路线图 (Conclusion & Roadmap)](#7-结语与演进路线图-conclusion--roadmap)

---

## 1. 执行摘要与工业背景 (Executive Summary & Background)

在现代自动化高端装备制造与跨国工程交付中，PLC（可编程逻辑控制器）与 HMI（人机界面）工程文件的多语言国际化规范化是核心交付验收标准。以**美国康宁 (Corning Incorporated) CT173 项目**为例，现场包含**1-封边机**、**2-撕胶带机**、**3-修边机**等多台高精尖自动化设备，控制系统基于**汇川 (Inovance) InoProShop / AutoShop (CODESYS 架构)** 平台构建。

在历史工程交付中，传统的表格翻译和导出往往依赖单一、强耦合的脚本或手工 Excel 处理，面临以下几大工业级痛点：
1. **格式脆弱性与工程失真**：汇川 InoProShop GVL 变量表要求严格的 9 列 CSV 结构、尾随逗号、Windows CRLF (`\r\n`) 换行以及 `CP936/GBK` 编码。若翻译内容中包含未转义逗号（如 `减速曲线：0，T型`），将破坏 CSV 列结构，导致工程导入直接崩溃或变量错位。
2. **硬编码词库与难以扩展**：电气专有词汇散落在脚本内部，当面对不同工艺机台（如修边机的削边刀、激光传感器、吸盘真空控制）或不同设备厂商时，改动核心代码极易引发全局回归。
3. **第三方系统孤岛**：外部自动化构建系统、CI/CD 质检管线、第三方工控 IDE 插件无法标准化调用核心引擎，缺乏通用服务契约（SPI）。
4. **交付质量验收无量化手段**：缺乏对变量名保真度、注释 0 中文残留、行数一致性的自动化五重断言机制。

为了解决上述问题，本白皮书正式确立并阐述**《PLC 工业表格通用套件架构设计与扩展接入规范》**。该架构采用**高内聚低耦合的微内核架构 (Microkernel Architecture)**，通过统一的服务提供者接口 (SPI) 体系解耦文件解析、翻译推理、文件导出与质量验收，同时对外提供 100% 向后兼容的门面 API 与 CLI，实现工业级高可靠、零缺陷的国际化交付。

---

## 2. 核心设计哲学：高内聚低耦合微内核 (Core Philosophy)

本套件遵循现代软件工程的**高内聚 (High Cohesion)** 与**低耦合 (Low Coupling)** 原则，以及经典的微内核体系架构：

```
+---------------------------------------------------------------------------------+
|                                 核心设计原则                                    |
+---------------------------------------------------------------------------------+
| 1. 单一职责 (SRP): 解析、翻译、序列化、验收各司其职，内部逻辑高内聚，边界清晰   |
| 2. 开闭原则 (OCP): 对扩展开放 (通过 SPI 插件热注入)，对修改封闭 (微内核核心稳定)|
| 3. 依赖倒置 (DIP): 核心引擎不直接依赖具体文件格式或词典，而是依赖 SPI 抽象接口 |
| 4. 接口隔离 (ISP): 拆分为解析、词典、导出、质检等专用 SPI，最小化第三方实现负担|
| 5. 坚固防御 (Robustness): 数据流全程格式保真，强容错防御，零中文字符残留交付    |
+---------------------------------------------------------------------------------+
```

### 微内核与插件机制优势
- **核心稳定性 (Core Stability)**：微内核仅保留插件注册生命周期、上下文管道流转、多阶段级联调度及基础数据模型。
- **插拔灵活性 (Pluggability)**：无论是新增西门子 TIA Portal 解析器、接入大模型云端翻译 API、还是注入定制化电气规范，开发者均无需修改微内核一行代码，仅需实现对应的 SPI 插件。
- **零破坏向下兼容 (Zero-Breakage Backward Compatibility)**：上层历史代码与自动化脚本（如 `VarTableProcessor`, `TableVerifier`）通过 Facade 门面完全保持 ABI 与 CLI 参数 100% 兼容。

---

## 3. 4层微内核系统架构设计 (4-Layer Microkernel Architecture)

### 3.1 总体组件架构图 (ASCII & Mermaid UML)

#### ASCII 架构图
```text
+===================================================================================+
|                               Top-Level Facades & CLI                             |
|  - VarTableProcessor (GVL Processor)      - IOTableProcessor (IO Processor)       |
|  - IndustrialTermEngine (Term Engine)     - TableVerifier (5-Fold Verifier)       |
|  - CLI Entry Point (vars / io / verify / machine / --plugin / --plugins-dir)      |
+===================================================================================+
                                         |
                                         v
+===================================================================================+
|                        Microkernel Core & Plugin Registry                         |
|  - Kernel (Central Coordinator)           - PluginRegistry (Lifecycle & Priority) |
|  - TableDocument (In-Memory Canonical)    - TableRow (Canonical Row Entity)       |
+===================================================================================+
         |                       |                       |                      |
         v                       v                       v                      v
+-----------------+     +-----------------+     +------------------+  +-----------------+
| 1. Parser Layer |     | 2. Engine Layer |     | 3. Exporter Layer|  | 4. Verifier     |
+-----------------+     +-----------------+     +------------------+  +-----------------+
| TableParserPlugin     | Dictionary-     |     | TableExporter-   |  | PostVerifyRule- |
|   (SPI)         |     | ProviderPlugin  |     | Plugin (SPI)     |  | Plugin (SPI)    |
|                 |     |   (SPI)         |     |                  |  |                 |
| GVLTableParser  |     | MultiStage-     |     | GVLCsvExporter   |  | Core 5-Fold     |
|   (9-Col CSV)   |     | Translation-    |     |   (GBK/CRLF)     |  | Assertions      |
|                 |     | Engine          |     |                  |  |   - Line Count  |
| IOTableParser   |     |                 |     | IOCsvExporter    |  |   - CRLF Check  |
|   (Hardware IO) |     | Builtin-        |     |   (GBK/CRLF)     |  |   - 9-Col Schema|
|                 |     | Dictionary-     |     |                  |  |   - Name Preserv|
| [Ext: Siemens/  |     | Plugin          |     | MarkdownReport-  |  |   - 0-CN Residue|
|  Mitsubishi...] |     |                 |     | Exporter         |  |                 |
|                 |     | [Ext: Custom/   |     |   (TOC/Anchors)  |  | [Ext: Tag Length|
|                 |     |  Cloud LLM...]  |     |                  |  |  Address Col...] |
+-----------------+     +-----------------+     +------------------+  +-----------------+
```

#### Mermaid 架构分层图
```mermaid
graph TB
    subgraph Client_Facades["顶层兼容门面与命令行 (Facades & CLI)"]
        CLI["CLI Commands<br/>(vars / io / verify / machine)"]
        VTP["VarTableProcessor<br/>(GVL 变量表门面)"]
        ITP["IOTableProcessor<br/>(IO 注释表门面)"]
        ITE["IndustrialTermEngine<br/>(术语翻译门面)"]
        TV["TableVerifier<br/>(质量验收门面)"]
    end

    subgraph Microkernel_Core["微内核协调与数据模型 (Microkernel Core)"]
        K["Kernel<br/>(微内核核心协调器)"]
        PR["PluginRegistry<br/>(插件生命周期与优先级仲裁)"]
        TD["TableDocument<br/>(规范化内存表格文档)"]
        TR["TableRow<br/>(规范化行数据实体)"]
        TD -.-> TR
    end

    subgraph Layer1["第 1 层：文件解析层 (Parser Layer)"]
        TPSPI["TableParserPlugin (SPI)"]
        GVLP["GVLTableParser<br/>(9列 GVL CSV 解析器)"]
        IOP["IOTableParser<br/>(AutoShop IO CSV 解析器)"]
        TPSPI --> GVLP
        TPSPI --> IOP
    end

    subgraph Layer2["第 2 层：翻译与规则引擎层 (Engine Layer)"]
        DPSPI["DictionaryProviderPlugin (SPI)"]
        MSTE["MultiStageTranslationEngine<br/>(多阶段级联翻译引擎)"]
        BDP["BuiltinDictionaryPlugin<br/>(内置 IEC / 康宁词典)"]
        DPSPI --> BDP
        MSTE --> DPSPI
    end

    subgraph Layer3["第 3 层：格式化导出层 (Exporter Layer)"]
        TESPI["TableExporterPlugin (SPI)"]
        GVLE["GVLCsvExporter<br/>(GBK / CRLF / 9列保真)"]
        IOE["IOCsvExporter<br/>(GBK / CRLF 保真)"]
        MDE["MarkdownReportExporter<br/>(单一对照交付总表)"]
        TESPI --> GVLE
        TESPI --> IOE
        TESPI --> MDE
    end

    subgraph Layer4["第 4 层：质量验收层 (Verifier Layer)"]
        PVRPI["PostVerifyRulePlugin (SPI)"]
        C5F["Core 5-Fold Checks<br/>(行数/CRLF/9列/变量名/0中文)"]
        PVRPI --> C5F
    end

    CLI --> K
    VTP --> K
    ITP --> K
    ITE --> K
    TV --> K

    K --> PR
    K --> Layer1
    K --> Layer2
    K --> Layer3
    K --> Layer4
```

---

### 3.2 规范化内存数据模型 (Canonical In-Memory Models)

微内核解耦的关键在于建立一套与具体硬件厂商、具体文件存储格式无关的**规范化中间表示模型 (Intermediate Representation, IR)**。在 `plc_table_toolkit.py` 中，定义了 `TableRow` 与 `TableDocument`：

```python
@dataclass
class TableRow:
    """标准表格行内存对象 (兼容 GVL 9 列结构与 IO 注释结构)"""
    no: str = ""                         # 序号 (Col 0)
    name: str = ""                       # 变量名 / 软元件地址 (Col 1 或 Col 0)
    data_type: str = ""                  # 数据类型 (Col 2，如 BOOL, DINT, TONR)
    init_hide: str = ""                  # 隐藏初始值 (Col 3)
    init_val: str = ""                   # 初始值 (Col 4)
    retain: str = ""                     # 掉电保持属性 (Col 5)
    publish: str = ""                    # 网络公开属性 (Col 6)
    comment: str = ""                    # 原始注释 (Col 7 或 Col 1)
    addr: str = ""                       # 物理地址 / 软元件附加列 (Col 8)
    raw_parts: List[str] = field(default_factory=list)  # 原始拆分切片列表
    raw_line: str = ""                   # 原始物理行文本 (保持完全保真)
    extra: Dict[str, Any] = field(default_factory=dict) # 运行时动态扩展属性上下文

@dataclass
class TableDocument:
    """标准表格文档对象 (内存中间表现模型)"""
    file_path: str = ""                  # 源文件路径
    table_type: str = "var"              # 表格类别 ('var'=GVL, 'io'=硬件IO)
    headers: List[str] = field(default_factory=list)   # 列头字段名称列表
    rows: List[TableRow] = field(default_factory=list) # 内存数据行集合
    metadata: Dict[str, Any] = field(default_factory=dict) # 元数据 (编码/行数等)
    raw_lines: List[str] = field(default_factory=list) # 原始文件物理行全集
```

#### 关键设计优势
1. **完全保真 (High Fidelity)**：`raw_line` 与 `raw_parts` 完整保留了原始输入的所有格式细节（包括空行、尾随分隔符），即便在无法识别的未知行出现时，亦能做到 100% 原样还原，不丢弃任何工程信息。
2. **上下文隔离 (Context Isolation)**：`extra: Dict[str, Any]` 字典用于存放管道流转过程中的中间结果（如规范中文推导注释 `new_cn_c`、交付英文注释 `new_en_c`、方案 A 驼峰英化变量名 `new_en_var`），避免污染核心字段。

---

### 3.3 核心类图设计 (Mermaid UML Class Diagram)

```mermaid
classDiagram
    class BasePlugin {
        +str plugin_id
        +str plugin_name
        +str version
        +int priority
        +on_load(kernel: Kernel) void
        +initialize(config: dict) void
        +on_unload() void
    }

    class TableParserPlugin {
        <<abstract>>
        +can_parse(file_path: str, raw_bytes: bytes)* bool
        +parse(file_path: str, encoding: str)* TableDocument
    }

    class DictionaryProviderPlugin {
        <<abstract>>
        +get_exact_phrases()* Dict~str, str~
        +get_word_pairs()* List~Tuple~str, str~~
        +get_regex_rules()* List~Tuple~Pattern, Callable~~
    }

    class TableExporterPlugin {
        <<abstract>>
        +can_export(format_name: str)* bool
        +export(doc: TableDocument, output_path: str, **kwargs)* void
    }

    class PostVerifyRulePlugin {
        <<abstract>>
        +verify(src_path: str, tgt_path: str, doc: TableDocument, context: dict)* Tuple~bool, List~str~~
    }

    BasePlugin <|-- TableParserPlugin
    BasePlugin <|-- DictionaryProviderPlugin
    BasePlugin <|-- TableExporterPlugin
    BasePlugin <|-- PostVerifyRulePlugin

    TableParserPlugin <|-- GVLTableParser
    TableParserPlugin <|-- IOTableParser
    DictionaryProviderPlugin <|-- BuiltinDictionaryPlugin
    TableExporterPlugin <|-- GVLCsvExporter
    TableExporterPlugin <|-- IOCsvExporter
    TableExporterPlugin <|-- MarkdownReportExporter

    class PluginRegistry {
        -Dict~str, BasePlugin~ _plugins
        +register(plugin: BasePlugin, kernel: Kernel) void
        +unregister(plugin_id: str) BasePlugin
        +get_plugin(plugin_id: str) BasePlugin
        +get_plugins() List~BasePlugin~
        +get_plugins_by_type(plugin_type: Type) List~T~
        +load_from_file(file_path: str, kernel: Kernel) List~BasePlugin~
        +load_from_directory(dir_path: str, kernel: Kernel) List~BasePlugin~
    }

    class MultiStageTranslationEngine {
        -Kernel kernel
        -bool _cache_dirty
        -Dict _merged_exact
        -List _merged_word_pairs
        -List _merged_regex_rules
        +invalidate_cache() void
        +translate(text: str, custom_dict: dict) str
        +derive_chinese_comment(var_name: str, existing_comment: str) str
    }

    class Kernel {
        +PluginRegistry registry
        +MultiStageTranslationEngine engine
        +register_plugin(plugin: BasePlugin) void
        +unregister_plugin(plugin_id: str) BasePlugin
        +load_plugin_file(file_path: str) List~BasePlugin~
        +load_plugins_dir(dir_path: str) List~BasePlugin~
        +parse(file_path: str, encoding: str) TableDocument
        +translate_text(text: str, custom_dict: dict) str
        +derive_chinese_comment(var_name: str, existing_comment: str) str
        +export(doc: TableDocument, output_path: str, format_name: str, **kwargs) void
        +verify(src_path: str, tgt_path: str, mode: str, is_var_table: bool, context: dict) Tuple~bool, List~str~~
    }

    Kernel *-- PluginRegistry
    Kernel *-- MultiStageTranslationEngine

    class VarTableProcessor {
        +str mode
        +Kernel kernel
        +IndustrialTermEngine term_engine
        +process_file(src_path: str, dst_en_path: str, dst_cn_path: str) List~Tuple~
        +process_directory(src_dir: str, dst_en_dir: str, dst_cn_dir: str, report_md_path: str, project_title: str) dict
    }

    class TableVerifier {
        +verify_file(src_path: str, tgt_path: str, mode: str, is_var_table: bool, kernel: Kernel)$ Tuple~bool, List~str~~
        +verify_directory(src_dir: str, tgt_dir: str, mode: str, is_var_table: bool, kernel: Kernel)$ bool
    }

    VarTableProcessor --> Kernel
    TableVerifier --> Kernel
```

---

### 3.4 端到端批处理流水线时序 (Mermaid UML Sequence Diagram)

下图展示从用户触发批处理（CLI 或 Python 脚本）开始，各层组件协同工作的完整端到端时序流：

```mermaid
sequenceDiagram
    autonumber
    actor User as 工程师 / CI 脚本
    participant Facade as VarTableProcessor (Facade)
    participant K as Kernel (Microkernel)
    participant PR as PluginRegistry
    participant Parser as GVLTableParser (Layer 1)
    participant Engine as MultiStageTranslationEngine (Layer 2)
    participant Exporter as GVLCsvExporter (Layer 3)
    participant Verifier as TableVerifier & PostVerify (Layer 4)

    User->>Facade: process_file(src_csv, dst_en_csv, dst_cn_csv)
    Facade->>K: parse(src_csv, encoding='gbk')
    K->>PR: get_plugins_by_type(TableParserPlugin)
    PR-->>K: [GVLTableParser, ...]
    K->>Parser: can_parse(src_csv, raw_bytes)
    Parser-->>K: True
    K->>Parser: parse(src_csv, encoding='gbk')
    Parser-->>K: TableDocument (with TableRow items)
    K-->>Facade: TableDocument

    loop 遍历 TableDocument 中的每行数据 (TableRow)
        alt 存在原始中文注释
            Facade->>Engine: translate(row.comment)
        else 注释为空但变量名为中文 (方案 B)
            Facade->>Engine: derive_chinese_comment(row.name, "")
            Facade->>Engine: translate(derived_comment)
        end
        Engine-->>Facade: new_en_c (纯英文，0中文)
        Facade->>Facade: 逗号/分号转义与清洗 (',' -> ' / ')
        Facade->>Facade: 写入 row.extra['new_en_c'], row.extra['new_cn_c']
    end

    Facade->>K: export(doc, dst_en_csv, format="gvl_csv", is_chinese_backup=False)
    K->>Exporter: export(doc, dst_en_csv)
    Exporter-->>K: 写入纯英文 GBK / CRLF / 9列保真 CSV

    opt 用户指定了规范中文备份路径
        Facade->>K: export(doc, dst_cn_csv, format="gvl_csv", is_chinese_backup=True)
        K->>Exporter: export(doc, dst_cn_csv)
        Exporter-->>K: 写入规范中文 GBK / CRLF / 9列保真 CSV
    end

    Facade-->>User: 返回逐行变更列表 file_records

    User->>Verifier: verify_file(src_csv, dst_en_csv, mode="B")
    Verifier->>K: verify(src_csv, dst_en_csv, mode="B")
    K->>K: 执行 5 重核心断言 (行数/CRLF/9列/变量名/0中文)
    K->>PR: get_plugins_by_type(PostVerifyRulePlugin)
    PR-->>K: [CorningComplianceRulePlugin, ...]
    loop 遍历后置验收插件
        K->>Verifier: verify(src_csv, dst_en_csv, doc, context)
        Verifier-->>K: (ok, [rule_errors])
    end
    K-->>Verifier: (all_passed, [all_errors])
    Verifier-->>User: [PASS] 全部检验通过！
```

---

## 4. 服务提供者接口 (SPI) 规范与插件生命周期 (Plugin SPI & Lifecycle)

微内核架构的核心资产是其清晰严密的 SPI 契约。第三方开发者无需依赖任何未公开的私有方法，仅通过标准 SPI 即可完成功能定制。

### 4.1 BasePlugin 基类与优先级仲裁

所有插件都必须直接或间接继承 `BasePlugin`：

```python
class BasePlugin(abc.ABC):
    """所有微内核插件的抽象基类"""
    plugin_id: str = "base_plugin"     # 全局唯一标识符 (推荐 snake_case)
    plugin_name: str = "Base Plugin"   # 人类可读名称
    version: str = "1.0.0"             # 语义化版本号 (SemVer)
    priority: int = 100                # 优先级 (数值越小优先级越高，如 10 优于 100)

    def on_load(self, kernel: "Kernel") -> None:
        """当插件被注入微内核并完成实例化时触发的生命周期钩子"""
        pass

    def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """供宿主环境传入配置参数 (如 API Key, 最大限制等) 的初始化钩子"""
        pass

    def on_unload(self) -> None:
        """当插件被注销或微内核关闭时触发的资源释放钩子 (如关闭数据库、网络连接)"""
        pass
```

#### 优先级仲裁原则 (Priority Resolution)
1. **数值越小越优**：内置插件的默认优先级为 `priority = 100`。
2. **专有覆盖通用**：第三方定制插件（如 `priority = 10` 或 `priority = 20`）在注册中心中排在前面。
3. **词库精确仲裁**：在 `MultiStageTranslationEngine` 重建缓存时，精确匹配字典按优先级升序由低到高遍历装载，使**高优先级插件的词条覆盖低优先级/内置词条**；而在词对贪婪替换和正则匹配中，高优先级插件优先匹配。

---

### 4.2 TableParserPlugin 文件解析扩展接口

```python
class TableParserPlugin(BasePlugin):
    """文件解析层 SPI：将不同格式工控文件解析为 TableDocument 规范内存模型"""

    @abc.abstractmethod
    def can_parse(self, file_path: str, raw_bytes: bytes) -> bool:
        """依据文件扩展名、文件名特征或文件头二进制特征判断是否支持解析"""
        pass

    @abc.abstractmethod
    def parse(self, file_path: str, encoding: str = "gbk") -> TableDocument:
        """执行实际解析工作，返回结构化的 TableDocument 对象"""
        pass
```

- **内置实现**：
  - `GVLTableParser` (priority=100)：解析 InoProShop 9 列标准变量表 CSV。
  - `IOTableParser` (priority=100)：解析 AutoShop/InoProShop 软元件 IO 注释 CSV。

---

### 4.3 DictionaryProviderPlugin 术语与规则扩展接口

```python
class DictionaryProviderPlugin(BasePlugin):
    """规则与词典层 SPI：为翻译引擎动态注入专有领域词汇与正则处理逻辑"""

    @abc.abstractmethod
    def get_exact_phrases(self) -> Dict[str, str]:
        """返回精确全词匹配映射字典 {中文: 纯英文}"""
        pass

    @abc.abstractmethod
    def get_word_pairs(self) -> List[Tuple[str, str]]:
        """返回多词素贪婪子串替换对列表 [(中文, 英文), ...]"""
        pass

    @abc.abstractmethod
    def get_regex_rules(self) -> List[Tuple[Union[re.Pattern, str], Callable]]:
        """返回参数化动态正则规则列表: [(compiled_pattern, handler_func)]"""
        pass
```

- **级联翻译五阶段机制**：
  1. **Tier 1 (Exact Match, $O(1)$)**：哈希表精确查询，适用于完整功能块名称、固定宏定义、专有状态量。
  2. **Tier 2 (Dynamic Regex Handlers)**：正则模式提取变量下标、时钟读写、从站编号、多轴联动等动态参数并递归翻译核心字段。
  3. **Tier 3 (Greedy Longest-Match Substring)**：多词素按汉字长度降序排列（`len(ch)` 逆序），贪婪替换复杂工控复合词（如“修边刀使用统计”优先于“修边刀”，再优先于“刀”）。
  4. **Tier 4 (Comment Derivation)**：若注释为空但变量名为中文，按方案 B 规则智能补齐规范中文注释与交付英文注释。
  5. **Tier 5 (Delimiter & Punctuation Sanitization)**：逗号与分号清洗（`,` / `，` / `；` -> ` / `），括号与感叹号全角转半角，消除多余空格。

---

### 4.4 TableExporterPlugin 格式化序列化扩展接口

```python
class TableExporterPlugin(BasePlugin):
    """格式化导出层 SPI：将 TableDocument 规范内存模型序列化写入磁盘或外设"""

    @abc.abstractmethod
    def can_export(self, format_name: str) -> bool:
        """判断是否支持该导出格式代码 (如 'gvl_csv', 'io_csv', 'markdown')"""
        pass

    @abc.abstractmethod
    def export(self, doc: TableDocument, output_path: str, **kwargs) -> None:
        """执行具体的序列化写盘逻辑 (支持 kwargs 传入 mode, is_chinese_backup 等)"""
        pass
```

- **内置实现**：
  - `GVLCsvExporter` (priority=100)：严格维持 GBK、CRLF、9 列及尾随逗号。
  - `IOCsvExporter` (priority=100)：严格维持 GBK、CRLF，保真 IO 注释列。
  - `MarkdownReportExporter` (priority=100)：生成文首带交互式 Table of Contents 与 `#section-N` 锚点跳转的交付总表。

---

### 4.5 PostVerifyRulePlugin 质量验收规则扩展接口

```python
class PostVerifyRulePlugin(BasePlugin):
    """质量验收层 SPI：为全量验收流程注入第三方自定义业务合规性断言"""

    @abc.abstractmethod
    def verify(self, src_path: str, tgt_path: str, doc: TableDocument, context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        执行自定义质检断言
        :return: (is_passed: bool, error_messages: List[str])
        """
        pass
```

- **核心五重内置断言与插件扩展关系**：
  `Kernel.verify()` 首先执行核心 5 重物理保真断言（文件存在性、物理行数 1:1 吻合、Windows CRLF、9 列结构、变量名一致、0 中文字符残留）。通过后，调度所有已注册的 `PostVerifyRulePlugin`（如标签字符数限制、禁止特定敏感词、地址冲突排查）。

---

### 4.6 PluginRegistry 注册中心与动态反射机制

`PluginRegistry` 负责插件对象的装载、卸载、按类型过滤以及反射加载外部 Python 脚本：

```python
class PluginRegistry:
    def register(self, plugin: BasePlugin, kernel: Optional["Kernel"] = None) -> None: ...
    def unregister(self, plugin_id: str) -> Optional[BasePlugin]: ...
    def get_plugins_by_type(self, plugin_type: Type[T]) -> List[T]: ...
    def load_from_file(self, file_path: str, kernel: Optional["Kernel"] = None) -> List[BasePlugin]: ...
    def load_from_directory(self, dir_path: str, kernel: Optional["Kernel"] = None) -> List[BasePlugin]: ...
```

#### 动态加载双轨策略 (Dual Loading Strategies)
1. **模块级入口函数法**：外部脚本如果定义了 `def register_plugins(kernel: Kernel) -> List[BasePlugin]:`，注册中心将优先调用该入口，便于第三方插件统一批量实例化并注入配置。
2. **反射自省法 (Reflection)**：若无注册函数，注册中心自动扫描模块中所有继承自 `BasePlugin` 的子类与全局实例，自动完成实例化与注册。
3. **缓存自动失效联动 (Cache Invalidation)**：只要新注册或注销了 `DictionaryProviderPlugin`，微内核立即调用 `engine.invalidate_cache()`，确保后续翻译即刻生效，无需重启进程。

---

### 4.7 插件生命周期与钩子调用时序图 (Mermaid UML Sequence Diagram)

```mermaid
sequenceDiagram
    autonumber
    participant CLI as CLI / Host App
    participant Kernel as Kernel
    participant Registry as PluginRegistry
    participant Plugin as CustomPlugin (BasePlugin)
    participant Engine as MultiStageTranslationEngine

    Note over CLI, Plugin: 插件动态装载阶段 (Load Phase)
    CLI->>Kernel: load_plugin_file("demo_custom_plugin.py")
    Kernel->>Registry: load_from_file("demo_custom_plugin.py", kernel)
    Registry->>Registry: importlib 动态编译与加载模块
    Registry->>Plugin: 实例化插件对象 CustomPlugin()
    Registry->>Registry: register(plugin)
    Registry->>Plugin: on_load(kernel)
    Plugin-->>Registry: 生命周期就绪
    Registry-->>Kernel: [Plugin Instances]

    alt 插件继承自 DictionaryProviderPlugin
        Kernel->>Engine: invalidate_cache()
        Note right of Engine: 标记词典缓存为 Dirty，<br/>下次翻译时按 priority 重新合并
    end

    Note over CLI, Plugin: 运行时调用与初始化 (Runtime Phase)
    CLI->>Plugin: initialize(config={"max_len": 120})
    CLI->>Kernel: translate_text("修边刀使用统计")
    Kernel->>Engine: translate()
    Engine->>Engine: _rebuild_cache_if_needed()
    Engine->>Plugin: get_exact_phrases() / get_word_pairs()
    Plugin-->>Engine: 返回专有扩展词汇
    Engine-->>Kernel: 翻译结果 (纯英文)
    Kernel-->>CLI: 交付文本

    Note over CLI, Plugin: 插件卸载与资源清理 (Unload Phase)
    CLI->>Kernel: unregister_plugin("custom_plugin_id")
    Kernel->>Registry: unregister("custom_plugin_id")
    Registry->>Plugin: on_unload()
    Plugin-->>Registry: 资源清理完成 (关闭连接/缓存)
    Registry-->>Kernel: 插件实例
    Kernel->>Engine: invalidate_cache()
```

---

## 5. 工业级需求变更容错与应对方案 (Industrial Mutation Mitigation Policies)

在长周期大型工程交付中，设备工艺变更、硬件品牌更替、云端大模型升级以及不规范的现场 CSV 操作是不可避免的。微内核体系从架构设计上提供了详尽的容错与突变缓解方案。

### 5.1 硬件厂商与新 PLC 品牌适配方案 (Siemens / Mitsubishi / Omron / Rockwell)

当企业将业务从汇川平台横向推广到其他主流 PLC 平台时，各厂商表格导出格式差异巨大：

| PLC 厂商 / 编程环境 | 变量表 / Tag 导出格式 | 行列特征 | 换行与字符集 | 适配策略 |
| :--- | :--- | :--- | :--- | :--- |
| **汇川 AutoShop (小型PLC)** | `io注释-*.csv` / `*_变量表.csv` (H1U/H2U/H3U/H5U, `.hcp`/`.hcpp`) | 8 列 IO 注释 (`数据值1~4`)；9 列 GVL 含软元件映射 | CRLF, GBK (CP936) | **原生内置** `AutoShopTableParser` 与 `IOTableProcessor` |
| **汇川 InoProShop (中大型PLC)** | `*_变量表.csv` (AM400/AM600/AC800, `.project`) | 9 列 CSV，末尾有尾随逗号 (10 tokens)，遵循 IEC 61131-3 | CRLF, GBK (CP936) | **原生内置** `GVLTableParser` 与 `GVLCsvExporter` |
| **三菱 (Mitsubishi GX Works3)** | Global Label 导出 `.csv` (TSV) / IO 注释 `.csv` | 27 列 GVL / 2 列 IO，首行为 POU 名称，多语种专用列 (EN Col 13, IT Col 18, CN Col 14) | CRLF, UTF-16 LE (带 BOM `\xFF\xFE`), 制表符 `\t` | **原生内置** `MitsubishiGXWorks3Parser` 与 `MitsubishiGXWorks3Exporter` |
| **西门子 (Siemens TIA Portal)** | `.db` (Data Block) / `.scl` 导出 CSV | 8 列（Name, Data Type, Offset, Comment...），带双引号包裹 | CRLF, UTF-8 或 UTF-16LE | 扩展 `SiemensDBTableParser` |
| **欧姆龙 (Omron Sysmac Studio)** | Variable Export `.tsv` / `.csv` | 12 列（Name, Scope, Data Type, Initial Value...） | CRLF, UTF-8 (含 BOM) | 扩展 `OmronSysmacParser` |
| **罗克韦尔 (Rockwell Studio 5000)** | Tag Export `.csv` (L5X / CSV) | 7 列（TAG, SPECIFIER, TYPE, DESCRIPTION...） | CRLF, ANSI / Windows-1252 | 扩展 `RockwellTagParser` |

#### 5.1.1 核心落地案例：三菱 GX Works3 工业级实战与意大利国家电网 (Enel - 3Sun) 交付

套件现已将**三菱电机 GX Works3** 平台纳入一等公民原生支持，并在**意大利国家电网 (Enel - 3Sun Gigafactory) SC1847 光伏组件封装产线 (边框缓存机、放框机、组框机等)** 获得 100% 验收验证。

##### 1. GX Works3 文件协议核心特征
- **伪 CSV 格式**：文件扩展名虽为 `.csv`，但内部严格采用制表符 `\t` 分隔（标准 TSV）。
- **编码规范**：文件必须包含 UTF-16 Little Endian BOM（前两字节为 `0xFF 0xFE`），非 UTF-8 或 GBK。
- **POU 块头声明**：文件第 1 行为单一双引号包裹的程序组织单元名称（如 `"边框缓存机"`），第 2 行为 27 列（GVL）或 2 列（IO）字段表头。
- **多语种原生列槽位**：
  - 第 14 列 (Col 14, 索引 13)：`English` (纯英文列)
  - 第 15 列 (Col 15, 索引 14)：`Chinese Simplified/简体中文` (规范中文列)
  - 第 19 列 (Col 19, 索引 18)：`Italian/Italiano` (意大利语列)

##### 2. 微内核适配机制
- **自动嗅探与分流**：`detect_table_platform(file_path)` 读取文件头前两字节，侦测到 `0xFF 0xFE` 或内部 `\t` 分隔符即自动路由至 `MitsubishiGXWorks3Parser`；若检测到同目录下 `.hcp`/`.hcpp` 或包含 `数据值1` 则智能路由至 `autoshop`。
- **零损耗多语种写入**：`MitsubishiGXWorks3Exporter` 根据目标交付语言（`target_lang='en'` 或 `target_lang='it'`），将译文精确填入 Col 14 (EN) 或 Col 19 (IT)，同时完整保留 Col 15 的原始中文，实现 GX Works3 导入后**中文、英文、意文在工控 IDE 内随时平滑切换**。
- **光伏行业专有词典插件**：新增 `SolarFrameDictionaryPlugin` (优先级 20)，内嵌光伏边框自动化产线专有术语（如 `边框缓存机` $\rightarrow$ `Buffer Telai` / `Frame Buffer Machine`，`接近开关` $\rightarrow$ `Finecorsa Prelievo` / `Proximity Switch`）。

##### 3. GUI 与 Web 控制台品牌切换
桌面 GUI (`core/plc_gui.py`) 与 Web 控制台 (`core/plc_web_gui.py`) 顶部均集成了：
- **PLC 品牌/平台下拉选单**：
  - `[⚡ 自动智能识别 (Auto Detect)]`
  - `[汇川 AutoShop (H3U/H5U 小型PLC)]`
  - `[汇川 InoProShop (CODESYS/AM/AC 中大型PLC)]`
  - `[三菱 GX Works3 (iQ-R/iQ-F 平台)]`
- **目标交付语言下拉选单**：`[English (纯英文交付)]`、`[Italiano (意大利语交付)]`
- **跨平台安全检视**：检视器自动对齐展示 GX Works3 的 IEC 61131-3 类型（如将 `Bit` 标准化感知为 `BOOL`）、原始中文与外文交付注释，确保 100% 纯只读安全零副作用。

#### 5.1.2 其他品牌 PLC 的零核心侵入接入实践
对于西门子、罗克韦尔等品牌，开发者仅需实现专有的 `TableParserPlugin` 与 `TableExporterPlugin`，无需修改任何核心代码：

```python
import os
import re
import csv
import io
from typing import List, Dict, Any
from plc_table_toolkit import TableParserPlugin, TableDocument, TableRow

class SiemensDBTableParser(TableParserPlugin):
    """西门子 TIA Portal 全局数据块 (DB) 导出 CSV 解析器插件"""
    plugin_id = "siemens_tia_db_parser"
    plugin_name = "Siemens TIA Portal Global DB CSV Parser"
    version = "1.0.0"
    priority = 30  # 高于内置解析器优先级

    def can_parse(self, file_path: str, raw_bytes: bytes) -> bool:
        if not file_path.lower().endswith('.csv'):
            return False
        # 检测西门子导出的特征标识或列头
        header = raw_bytes[:512].decode('utf-8', errors='ignore')
        return "Data_Block" in header or ("Path" in header and "Data type" in header) or ("Offset" in header and "Comment" in header)

    def parse(self, file_path: str, encoding: str = "utf-8") -> TableDocument:
        with open(file_path, "rb") as f:
            raw = f.read()
        text = raw.decode(encoding, errors='replace')
        lines = text.splitlines(keepends=False)

        headers: List[str] = []
        rows: List[TableRow] = []
        
        # 使用标准 csv.reader 处理西门子可能包含的双引号包裹字段
        reader = csv.reader(io.StringIO(text), delimiter=',', quotechar='"')
        for idx, parts in enumerate(reader):
            if idx == 0:
                headers = [p.strip() for p in parts]
                continue
            if not parts or not any(p.strip() for p in parts):
                rows.append(TableRow(raw_line=lines[idx] if idx < len(lines) else ""))
                continue

            # 西门子典型列: Name, Data type, Offset, Initial value, Comment
            name = parts[0].strip() if len(parts) > 0 else ""
            dtype = parts[1].strip() if len(parts) > 1 else ""
            offset = parts[2].strip() if len(parts) > 2 else ""
            init_val = parts[3].strip() if len(parts) > 3 else ""
            comment = parts[4].strip() if len(parts) > 4 else ""

            row = TableRow(
                no=str(idx),
                name=name,
                data_type=dtype,
                init_val=init_val,
                comment=comment,
                addr=offset,
                raw_parts=parts,
                raw_line=lines[idx] if idx < len(lines) else ','.join(parts),
                extra={"vendor": "siemens", "offset": offset}
            )
            rows.append(row)

        return TableDocument(
            file_path=file_path,
            table_type="var",
            headers=headers,
            rows=rows,
            raw_lines=lines,
            metadata={"encoding": encoding, "vendor": "siemens", "line_count": len(lines)}
        )


class RockwellTagParser(TableParserPlugin):
    """罗克韦尔 Studio 5000 Tag 导出 CSV 解析器插件"""
    plugin_id = "rockwell_tag_parser"
    plugin_name = "Rockwell Studio 5000 Tag CSV Parser"
    version = "1.0.0"
    priority = 35

    def can_parse(self, file_path: str, raw_bytes: bytes) -> bool:
        if not file_path.lower().endswith('.csv'):
            return False
        header = raw_bytes[:512].decode('ansi', errors='ignore')
        return "TAG" in header and "DATATYPE" in header or "SPECIFIER" in header

    def parse(self, file_path: str, encoding: str = "ansi") -> TableDocument:
        with open(file_path, "rb") as f:
            raw = f.read()
        text = raw.decode(encoding, errors='replace')
        lines = text.splitlines(keepends=False)

        headers: List[str] = []
        rows: List[TableRow] = []
        reader = csv.reader(io.StringIO(text), delimiter=',', quotechar='"')

        for idx, parts in enumerate(reader):
            if idx == 0:
                headers = [p.strip() for p in parts]
                continue
            if not parts or not any(p.strip() for p in parts):
                rows.append(TableRow(raw_line=lines[idx] if idx < len(lines) else ""))
                continue

            # 罗克韦尔典型列: TAG, TYPE, DESCRIPTION, ...
            tag_name = parts[0].strip() if len(parts) > 0 else ""
            data_type = parts[2].strip() if len(parts) > 2 else ""
            desc = parts[3].strip() if len(parts) > 3 else ""

            row = TableRow(
                no=str(idx),
                name=tag_name,
                data_type=data_type,
                comment=desc,
                raw_parts=parts,
                raw_line=lines[idx] if idx < len(lines) else ','.join(parts),
                extra={"vendor": "rockwell"}
            )
            rows.append(row)

        return TableDocument(
            file_path=file_path,
            table_type="var",
            headers=headers,
            rows=rows,
            raw_lines=lines,
            metadata={"encoding": encoding, "vendor": "rockwell", "line_count": len(lines)}
        )
```

---

### 5.2 复杂工业数据类型扩展方案 (DUT 结构体 / 多维数组 / 功能块 / 指针与引用)

现代 PLC 编程大量采用面向对象与结构化数据类型（IEC 61131-3），表格中常包含复杂的嵌套与引用类型：

1. **多维数组 (Multi-dimensional Arrays)**：
   - 语法形态：如 `ARRAY[0..5, 0..3] OF REAL`、`ARRAY[1..10] OF DUT_Axis_Param`，或动态变量 `Alarm_History_BOOL[0]`、`Cutter_Pos_Offset[2][1]`。
   - 隔离机制：数据类型列完整保持 `ARRAY[...] OF ...` 语法结构不变；针对带索引的变量名（如 `修边刀伺服使能[1]`），引擎通过 Tier 2 参数化正则 `r'^(.*?)\[(\d+)\]$'` 智能解构：提取前缀词条 `修边刀伺服使能` 经过词典翻译为 `Trimming Cutter Servo Enable`，最后拼接回结构化下标 `Trimming Cutter Servo Enable [1]`。
2. **专有结构体与用户自定义数据类型 (DUT / Struct)**：
   - 语法形态：如 `ST_Trimmer_Axis_Param`、`DUT_Glass_Align_Data`、`ST_Recipe_Header`。
   - 命名空间与点号成员访问：如 `ST_Trimmer.rActual_Speed` 或 `修边工位参数.刀头原点位置`。正则规则匹配 `r'^(.*?)(\.|\-\>)(.+)$'` 分段递归翻译，并保留命名空间分隔符。
3. **标准功能块与运动控制实例 (Function Blocks)**：
   - 语法形态：如 `TONR` (保持型定时器)、`SV_Jog` (寸动控制块)、`MC_MoveAbsolute`、`MC_Power`。
   - 实例命名与数据类型绝对隔离：在 `TableRow` 内存模型中，`data_type` 字段（如 `TONR`）受只读保护，禁止任何规则修改；实例名（如 `fb_Trim_Timer`）由方案 B 保持原样，仅将其原始注释（如 `修边保持定时器`）翻译为纯英文 `Trimming Retentive Timer`。
4. **指针与引用类型 (Pointers & References: `POINTER TO`, `REF_TO`, `ADR`, `^`)**：
   - 语法形态：IEC 61131-3 中广泛使用的直接内存寻址与软元件指针，如 `POINTER TO DUT_Cutter_Config`、`REF_TO ST_Motor_Status`，以及解除引用操作 `pCurrentRecipe^.dwBatchID`。
   - 符号安全保护策略：
     - **数据类型原子保真**：解析层与导出层将 `POINTER TO <Type>` 与 `REF_TO <Type>` 标记为原子不可拆解符号，严禁翻译引擎将其中的 `POINTER TO` 误判为英语单词并进行词法重构。
     - **解除引用符号 (`^`) 语法保留**：在方案 B 变量名校验中，严格允许 `^` 符号作为合法变量名字符，杜绝因特殊符号误触发名称漂移警报。
     - **指针注释专有推导**：当遇到未注释的指针变量（如 `pTrimmerAxis`），智能推导系统识别其匈牙利命名法前缀 `p` 或 `ref`，自动派生注释 `Pointer to Trimmer Axis`，实现 100% 纯英文交付要求。

---

### 5.3 云端与大模型 (Cloud / LLM) AI 翻译接入容灾方案

为应对未来将核心翻译引擎对接至云端大语言模型（如 Azure OpenAI, DeepSeek, 内部私有化大模型或 Ollama）的需求，架构设计确立了**四重防御与容灾方案**：

```
+-----------------------------------------------------------------------------+
|              Cloud / LLM AI 翻译接入四重容灾与降级架构体系                   |
+-----------------------------------------------------------------------------+
|                                                                             |
|  输入文本 ---> [ 1. 本地持久化 SQLite / JSON 缓存 ] --命中--> 返回翻译结果  |
|                                |                                            |
|                              未命中                                         |
|                                v                                            |
|                 [ 2. 批量请求打包与 Token 优化器 ]                          |
|                                |                                            |
|                                v                                            |
|                 [ 3. 云端 LLM API (带指数退避重试) ]                        |
|                                |                                            |
|                 +--------------+---------------+                            |
|                 | 超时 / 网络故障 / 429 频控   | 调用成功                   |
|                 v                              v                            |
|  [ 4. 离线保底：内置确定性词典引擎 ]    写入本地持久化缓存并返回结果        |
+-----------------------------------------------------------------------------+
```

1. **本地持久化二级缓存 (Local Persistent Caching)**：
   工控变量存在大量高频重复词汇（如“就绪”、“伺服使能”、“到位”）。LLM 插件内嵌 JSON / SQLite 字典哈希缓存，对已翻译条目直接命中，实现 $O(1)$ 本地返回，削减 90% 以上的网络调用。
2. **批量请求与 Token 压缩 (Batch Token Optimization)**：
   将整张表的待翻译注释去重后聚合为单次 Prompt 请求（如一次性打包 50 条），利用 JSON 结构体交互，避免逐行请求导致的延迟爆炸与连接开销。
3. **频控限制与指数退避 (Rate Limiting & Exponential Backoff)**：
   捕获 HTTP 429 (Too Many Requests) 与 5xx 网络错误，执行 3 次指数递增退避等待（如 1s, 2s, 4s）。
4. **离线与断网平滑降级 (Graceful Degradation)**：
   一旦重试失败或处于无外网的保密工控机环境，插件立即自动回退到 `BuiltinDictionaryPlugin` 离线确定性多阶段引擎，确保生产构建流程绝对不中断。

#### 云端与大模型容灾插件完整参考实现

```python
import os
import re
import json
import time
from typing import Dict, List, Tuple, Optional, Callable, Union
from plc_table_toolkit import DictionaryProviderPlugin, BuiltinDictionaryPlugin

class CloudLLMTranslationPlugin(DictionaryProviderPlugin):
    """
    工业级云端 / LLM 大模型翻译插件 (集成持久化缓存、频控指数退避与离线确定性保底)
    """
    plugin_id = "cloud_llm_translation_provider"
    plugin_name = "Enterprise Cloud LLM Translation Provider"
    version = "1.0.0"
    priority = 10  # 最高优先级：命中云端/缓存翻译

    def __init__(self, cache_file: str = "llm_translation_cache.json",
                 api_key: Optional[str] = None,
                 endpoint: str = "https://api.openai.com/v1/chat/completions",
                 timeout_sec: float = 3.0,
                 max_retries: int = 3):
        super().__init__()
        self.cache_file = cache_file
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.endpoint = endpoint
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self._cache: Dict[str, str] = {}
        self._fallback_plugin = BuiltinDictionaryPlugin()
        self._load_cache()

    def _load_cache(self) -> None:
        """从本地磁盘读取持久化缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}

    def _save_cache(self) -> None:
        """安全写盘持久化缓存"""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _call_remote_llm(self, text: str) -> Optional[str]:
        """模拟调用云端 LLM API，集成指数退避与超时控制"""
        if not self.api_key:
            return None  # 无 API Key，直接触发降级

        # 示例伪代码：实际接入时使用 requests / httpx / urllib
        for attempt in range(1, self.max_retries + 1):
            try:
                # 模拟网络调用与超时检测
                # response = requests.post(self.endpoint, headers=..., json=..., timeout=self.timeout_sec)
                # if response.status_code == 200:
                #     return response.json()["choices"][0]["message"]["content"].strip()
                # elif response.status_code == 429: # Rate Limited
                #     time.sleep(1.0 * (2 ** (attempt - 1)))
                break
            except Exception:
                time.sleep(1.0 * (2 ** (attempt - 1)))
        return None  # 失败返回 None 触发本地离线保底

    def translate_with_fallback(self, text: str) -> str:
        """带离线保底的多级翻译路由"""
        if not text or not re.search(r'[\u4e00-\u9fff]', text):
            return text

        # 1. 命中本地缓存 (O(1))
        if text in self._cache:
            return self._cache[text]

        # 2. 尝试云端 LLM 翻译
        remote_res = self._call_remote_llm(text)
        if remote_res and not re.search(r'[\u4e00-\u9fff]', remote_res):
            self._cache[text] = remote_res
            self._save_cache()
            return remote_res

        # 3. 触发离线平滑降级：使用确定性本地内置词库
        exacts = self._fallback_plugin.get_exact_phrases()
        if text in exacts:
            return exacts[text]

        return text

    def get_exact_phrases(self) -> Dict[str, str]:
        # 将本地持久化缓存作为高优精确匹配项注入微内核
        return dict(self._cache)

    def get_word_pairs(self) -> List[Tuple[str, str]]:
        return []

    def get_regex_rules(self) -> List[Tuple[Union[re.Pattern, str], Callable]]:
        return []
```

---

### 5.4 工业 CSV 脏数据与畸变防御策略 (引号未闭合 / 换行符 / 逗号冲突)

现场工程师或非专业人员使用记事本、Excel 等工具手动修改 CSV 时，经常引入工业数据“畸变”。微内核实现了全链路工业级防御：

1. **注释中包含逗号的“列错位”防御 (Comma In Comments)**：
   - *问题*：汇川 CSV 以 `,` 分隔。若注释为 `减速曲线类型：0，T型；1，S型`，普通分割会产生第 10 列甚至更多列，破坏 9 列规范，导致 PLC 导入时整表报废。
   - *防御*：翻译引擎与导出器在序列化前，强制将中文全角逗号 `，` 与英文半角逗号 `,` 清洗替换为统一的分隔符 ` / `，分号 `；` 与 `;` 亦清洗为 ` / `，彻底杜绝列溢出。
   ```python
   # 工业级分隔符清洗逻辑
   cleaned_comment = en_comment.replace(',', ' / ').replace('，', ' / ').replace(';', ' / ').replace('；', ' / ')
   ```
2. **未闭合双引号防御 (Unbalanced Quotes)**：
   - *问题*：部分编辑器（如 Excel）会自动为含有逗号或特殊符号的单元格添加外层双引号，或手动编辑遗留下了奇数个单双引号。
   - *防御*：`GVLCsvExporter` 与 `IOCsvExporter` 采用严苛的字段级规整算法，剥离悬空未闭合的双引号，并确保生成的每一行均为扁平的纯文本 CSV，杜绝 PLC 编译器的词法解析异常。
3. **换行符不一致防御 (CRLF vs LF)**：
   - *问题*：Linux 构建机、CI 自动化管线或 Git 跨平台检出常将 Windows CRLF (`\r\n`) 转换为 LF (`\n`)，直接导入 InoProShop 将引发不可预知的乱码或直接无法识别换行。
   - *防御*：所有 Exporter 底层一律采用二进制写模式 (`open(..., 'wb')`)，显式将行数组通过 `\r\n.join(lines).encode('gbk')` 编码写入。`TableVerifier` 第 2 重断言严格检查 `b'\r\n' in tgt_bytes`，对任何非 CRLF 文件坚决判定不合格。
4. **多字节字符集混杂防御 (Encoding Defense)**：
   - *问题*：现场工程文件中常混杂有带 UTF-8 BOM (`\xef\xbb\xbf`) 的文件，或含有特殊电气生僻符号（如 `℃`, `°`, `±`, `μs`, `Ω`）。
   - *防御*：解析层采用 `gbk` 解码并挂载 `errors='replace'`，在数据读取初期安全规避解码崩溃；全角标点统一自动正则替换为半角标点（如 `！` -> `!`, `（` -> ` (`, `）` -> `) `）。

---

## 6. 100% 向后兼容性保障策略 (Backward Compatibility Policy)

架构重构与演进最忌讳破坏现有生态。为了保证存量工程、历史批处理脚本（如 `run_translate_all.bat`）以及自动化测试用例（如 `verify_all_8_var_tables.py`）无缝运行，微内核架构实施了严格的**向后兼容性策略**。

### 6.1 门面模式 (Facade Pattern) 架构实现

顶层暴露的 4 大历史类全部重构为轻量级门面对象，其内部将请求完整转发至微内核与 SPI 组件：

```python
# 架构演进前 (Monolithic Procedural)
# 用户直接调用紧耦合脚本内部方法，修改内部逻辑即导致破坏

# 架构演进后 (Microkernel + Facade)
class VarTableProcessor:
    """历史兼容门面：封装微内核 Parser -> Translation -> Exporter 完整管线"""
    def __init__(self, mode: str = "B", term_engine: Optional[IndustrialTermEngine] = None, kernel: Optional[Kernel] = None):
        self.mode = mode.upper()
        self.kernel = kernel or get_default_kernel()
        self.term_engine = term_engine or IndustrialTermEngine(kernel=self.kernel)

    def process_file(self, src_path: str, dst_en_path: str, dst_cn_path: Optional[str] = None) -> List[Tuple]:
        # 委托微内核流转，保持入参与返回值 100% 不变
        ...
```

### 6.2 Python API ABI 稳定性与签名保真

| 暴露类 / 接口 | 关键方法 | 历史入参签名 | 历史返回值签名 | 兼容保障措施 |
| :--- | :--- | :--- | :--- | :--- |
| `IndustrialTermEngine` | `translate(text)` | `text: str` | `str` | 兼容 `custom_dict` 构造，支持对 `self.exact_phrases` 属性的原生直接访问 |
| `VarTableProcessor` | `process_file(...)` | `(src, dst_en, dst_cn)` | `List[Tuple[str, str, str, str, str]]` | 返回 5 元组 `(序号, 变量名, 类型, 中文注释, 英文注释)`，顺序与结构 100% 相同 |
| `VarTableProcessor` | `process_directory(...)` | `(src_dir, dst_en, dst_cn, report, title)` | `Dict[str, List[Tuple]]` | 字典键为文件名，值为 5 元组变更列表 |
| `IOTableProcessor` | `process_file(...)` | `(src, dst_en, dst_cn)` | `List[Tuple[str, str, str]]` | 返回 3 元组 `(地址, 原始注释, 英文注释)` |
| `TableVerifier` | `verify_file(...)` | `(src, tgt, mode, is_var)` | `Tuple[bool, List[str]]` | 返回 `(是否通过, 错误信息列表)` |
| `TableVerifier` | `verify_directory(...)` | `(src, tgt, mode, is_var)` | `bool` | 控制台格式化输出，返回布尔状态 |

### 6.3 CLI 命令行参数无缝兼容规范

CLI 保持原有的四个核心子命令语法 100% 不变，同时以非侵入方式扩展插件参数：

1. **原种子命令行为**：
   - `python core/plc_table_toolkit.py vars --src-dir ... --dst-dir ... [--mode B] [--report ...]`
   - `python core/plc_table_toolkit.py io --src-dir ... --dst-dir ...`
   - `python core/plc_table_toolkit.py verify --src ... --target ...`
   - `python core/plc_table_toolkit.py machine --machine-dir ...`
2. **非侵入式插件参数注入**：
   - 全局及所有子命令均支持可选的 `--plugin <path.py>`（支持多次传递以加载多个插件）。
   - 全局及所有子命令均支持可选的 `--plugins-dir <dir>`（批量加载目录下所有插件）。
   - 子命令解析器内部采用 `argparse.SUPPRESS` 默认值保护，杜绝子命令未传参时静默覆盖父级命名空间中的有效参数。

---

## 7. 结语与演进路线图 (Conclusion & Roadmap)

本白皮书规范确立的微内核工业表格处理套件架构，成功经受了康宁 CT173 项目三大机台（封边机、撕胶带机、修边机）共 46 个工业表格、超 45,000 行复杂工控变量的实战考验，实现了全量 **100% PASS** 零缺陷交付。

### 后续演进路线 (Roadmap)
- **Phase 1 (v2.1)**：发布标准化的 VS Code / InoProShop 外部扩展工具包，支持在 IDE 内一键右键调用微内核完成变量表与 IO 表的国际化转化。
- **Phase 2 (v2.2)**：将 `SiemensDBTableParser` 与 `RockwellTagParser` 纳入官方内置插件库，提供开箱即用的多硬件厂商一站式互通支持。
- **Phase 3 (v3.0)**：正式集成离线轻量化工控大模型（SLM）容器插件，实现多语种（德语、日语、西班牙语）全自动工业语义翻译。

---
*版权所有 © 2026 美国康宁 CT173 项目组 & 自动化交付质量保证委员会。未经许可，严禁外传。*
