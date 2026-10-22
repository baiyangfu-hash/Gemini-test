# `core/plc_table_toolkit.py` 模块说明

> 基于对源码的通读整理(2313 行,单文件)。行号对应提交 `0728ec7`,代码变动后可能偏移。
> 本文只描述代码**实际做了什么**,与《架构白皮书》中的设计意图互补;文末"阅读中发现的行为与注意点"是阅读所得,未全部另行验证。

## 1. 一句话概括

把汇川 InoProShop / AutoShop 的 GVL 变量表、IO 注释表(GBK CSV)以及三菱 GX Works3 的标签表(UTF-16 TSV)解析成统一的内存模型,经多阶段翻译引擎把中文注释译成英文,再按原平台格式导出,并做质量校验。所有环节(解析、词典、导出、校验)都是可插拔的插件。

## 2. 文件分区(按行号)

| 行号 | 分区 | 内容 |
|---|---|---|
| 1–38 | 文件头 | 模块文档、标准库导入、尝试把 stdout 切到 UTF-8 |
| 40–70 | 1. 数据模型 | `TableRow`、`TableDocument` |
| 72–150 | 2. 插件接口 | `BasePlugin` 及四类 SPI |
| 152–871 | 3. 内置词库 | `BUILTIN_EXACT_PHRASES`(100 条,156 行起)、`BUILTIN_WORD_PAIRS`(601 条,269 行起) |
| 874–1456 | 4. 内置插件 | 词典插件、两个汇川解析器、三个导出器、三菱解析器与导出器 |
| 1459–1501 | 平台嗅探 | `detect_table_platform()` |
| 1504–1971 | 5. 微内核 | `PluginRegistry`、`MultiStageTranslationEngine`、`Kernel`、默认单例、领域插件自动挂载 |
| 1975–2203 | 6. 兼容门面 | `IndustrialTermEngine`、`VarTableProcessor`、`IOTableProcessor`、`TableVerifier` |
| 2206–2313 | 7. CLI | `main()`,子命令 `vars` / `io` / `verify` / `machine` |

## 3. 数据模型

**`TableRow`**(44 行)是一行数据的统一表示:`no`、`name`、`data_type`、`init_hide`、`init_val`、`retain`、`publish`、`comment`、`addr` 对应汇川 9 列;`raw_parts` 保存原始拆分列,`raw_line` 保存原始行文本,`extra` 是自由字典。

`extra` 是各环节之间传递结果的约定通道,常见键:

| 键 | 写入方 | 读取方 |
|---|---|---|
| `new_en_c` | 处理器(翻译后的英文注释) | 各导出器 |
| `new_cn_c` | 处理器(规范中文注释) | 中文备份导出 |
| `new_en_var` | `VarTableProcessor`(仅方案 A) | `GVLCsvExporter` |
| `c_idx` | `IOTableParser`(注释所在列号) | IO 导出器 |
| `class` / `comment_orig` / `comment_en` / `comment_cn` / `comment_it` / `tokens_count` | `MitsubishiGXWorks3Parser` | 三菱导出与校验 |

**`TableDocument`**(61 行):`file_path`、`table_type`(`"var"` 或 `"io"`)、`headers`、`rows`、`raw_lines`、`metadata`(编码、行数、平台、POU 标题等)。

## 4. 插件接口(SPI)

所有插件继承 `BasePlugin`:`plugin_id`、`plugin_name`、`version`、`priority`(**数值越小优先级越高**,默认 100),以及钩子 `on_load(kernel)`、`initialize(config)`、`on_unload()`。

| 接口 | 必须实现 | 作用 |
|---|---|---|
| `TableParserPlugin` | `can_parse(path, raw_bytes)`、`parse(path, encoding)` | 文件 → `TableDocument` |
| `DictionaryProviderPlugin` | `get_exact_phrases()`、`get_word_pairs()`、`get_regex_rules()` | 提供术语 |
| `TableExporterPlugin` | `can_export(format_name)`、`export(doc, path, **kwargs)` | `TableDocument` → 文件 |
| `PostVerifyRulePlugin` | `verify(src, tgt, doc, context)` → `(bool, [错误])` | 追加质检规则 |

四个词典方法都是抽象方法,即使只想提供其中一类,其余也要返回空 dict 或空 list。

## 5. 内置插件

默认 `Kernel()` 会注册下列 8 个(`Kernel._register_builtins`,1768 行):

| 插件 | priority | 说明 |
|---|---|---|
| `MitsubishiGXWorks3Parser` | 50 | 识别 UTF-16 BOM、含制表符且带三菱特征列名的文件;27 列 TSV;首行若是单独的引号字符串则作为 POU 标题 |
| `GVLTableParser` | 100 | `.csv`,无 UTF-16 BOM、前 512 字节无制表符,且文件名含"变量表"或表头含"序号"+"变量名" |
| `IOTableParser` | 100 | `.csv`,文件名以 `io` / `IO` 开头 |
| `BuiltinDictionaryPlugin` | 100 | 内置词库 + 8 条参数化正则 |
| `GVLCsvExporter` | 100 | 格式名 `gvl_csv` / `var_csv` / `csv`;GBK + CRLF,补回 9 列和尾随逗号 |
| `IOCsvExporter` | 100 | 格式名 `io_csv` |
| `MitsubishiGXWorks3Exporter` | 50 | 格式名 `mitsubishi` / `gx_works3` / `gx3` / `gxworks3`;UTF-16、制表符、CRLF |
| `MarkdownReportExporter` | 100 | 格式名 `markdown` / `md` / `report`;生成带目录与锚点的中英对照总表 |

**解析顺序**:`Kernel.parse` 按 priority 升序遍历解析器,第一个 `can_parse` 为真的负责解析,所以三菱解析器(50)先于汇川解析器(100)。

**GVL 解析细节**(`GVLTableParser.parse`):首行作表头;列数 ≥ 8 才视为数据行;列数 > 10 时把第 7 列到倒数第 3 列用逗号重新拼回注释,用来容忍注释中未转义的逗号;空行保留为空 `TableRow`。

**GVL 导出细节**:英文版把注释里的 `,` 和 `，` 换成 ` / `,中文版把 `,` 换成全角 `，`;方案 A 额外改写变量名(第 1 列);每行 `','.join(parts[:9]) + ','`。

**三菱导出**:变量表把译文写入第 13 列(英文)或第 18 列(意大利语);`update_comment_col=True` 时同时覆盖第 7 列;第 14 列(中文)仅在为空时用规范中文补入;行不足 27 列时补空列。

### 内置正则规则(938 行)

| 模式 | 示例 → 结果 |
|---|---|
| `PLC时钟(读出\|写入)_(年\|月\|…)` | `PLC时钟读出_年` → `PLC Clock Read Year` |
| `NN_(产量统计区间时间段\|分\|…)` | `08_时` → `08:00 Hour` |
| `N#远程I/O模块链接异常` | → `#N Remote I/O Module Link Error!` |
| `EtherCAT从站N通讯异常` | → `EtherCAT Slave N Comm Error!` |
| `(Fnn)_xxx` | → `(Fnn) <译文>` |
| `1/2/3轴xxx` | → `Axis 1/2/3 <译文>` |
| `轴N：xxx` | → `Axis N: <译文>` |
| `xxx[N]` | → `<译文> [N]` |

## 6. 微内核

### `PluginRegistry`(1510 行)
- `register` 以 `plugin_id` 为键存入字典,**同名会直接覆盖**;`on_load` / `on_unload` 里的异常被吞掉。
- `get_plugins_by_type(cls)` 按 priority 升序返回。
- `load_from_file`:用 `importlib` 加载 `.py`;若模块里有 `register_plugins(kernel)` 先调用它,然后扫描模块里的 `BasePlugin` 实例和子类(会无参实例化每个子类,`plugin_id` 已存在则跳过)。
- `load_from_directory`:加载目录下不以 `.` 或 `_` 开头的 `.py`,单个文件失败只打印警告。

### `MultiStageTranslationEngine`(1598 行)
翻译走四级流水线,`translate(text, custom_dict, target_lang)`:

0. 前置:空串返回 `""`;不含中文直接原样返回;`custom_dict` 精确命中优先;`target_lang == "it"` 时先查各词典插件上**鸭子类型**的 `get_exact_phrases_italian()`,再尝试导入 `SolarFrameDictionaryPlugin.EXACT_PHRASES_IT`。
1. **Exact**:整串精确匹配。
2. **Regex**:依次尝试各正则,第一个返回非 `None` 的处理函数胜出;处理函数可通过第二个参数递归调用翻译。
3. **Greedy**:对 `word_pairs` 做子串替换,替换结果两侧加空格。
4. **规范化**:全角标点转半角、`，` `；` 转 ` / `、压缩空白。

**缓存与优先级**(`_rebuild_cache_if_needed`):
- 精确短语:按 priority **降序**遍历、后写覆盖先写,因此 priority 数值小的插件胜出。
- 词对:按 priority 升序收集,再按词长**降序稳定排序**。结果是**长度优先于优先级**——更长的词条先替换,同长度才看插件优先级。
- 缓存由 `Kernel.register_plugin` / `unregister_plugin` / `load_plugin_file` / `load_plugins_dir` 主动失效;直接调用 `registry.register` 不会失效。
- 词典插件的任何方法抛异常或返回类型不对,只会打印警告并跳过该插件的该部分。

### `Kernel`(1760 行)
持有一个 `PluginRegistry` 和一个引擎,提供 `register_plugin`(别名 `register`)、`unregister_plugin`(别名 `unregister`)、`load_plugin_file`、`load_plugins_dir`、`parse`、`translate_text`、`derive_chinese_comment`、`export`、`verify`。

**`Kernel.verify`(1833 行)** 的"5 重断言":

| # | 检查 | 适用 |
|---|---|---|
| 1 | 源/目标行数相等 | 全部 |
| 2 | 目标含 CRLF | 全部 |
| 3 | 列数充足(汇川 ≥ 9 列,三菱 ≥ 15 列) | 变量表 |
| 4 | 变量名未被改动 | **仅方案 B** |
| 5 | 交付列无中文残留(汇川第 7 列;三菱第 13/18 列;IO 注释列) | 全部 |

此外还会调度所有已注册的 `PostVerifyRulePlugin`。三菱与汇川通过目标文件的 BOM / 制表符区分。每个文件遇到第一处列级错误就 `break`,所以一次最多报告一个列级问题。

### 其他模块级函数
- `detect_table_platform(path)`:读前 2 KB 嗅探,返回 `autoshop` / `inoproshop` / `mitsubishi` / `unknown`。BOM 或制表符 → 三菱;含"数据值"或"软元件" → autoshop;含"序号"+"变量名" → 工程目录下有 `.hcp` / `.hcpp` 则 autoshop,否则 inoproshop;其余兜底返回 `autoshop`。
- `find_plugins_dir()` / `auto_load_domain_plugins(kernel)`:查找 `plugins/` 并加载 `trimmer_dictionary_plugin.py`(priority 10)和 `solar_frame_dictionary_plugin.py`(priority 20)。
- `_DEFAULT_KERNEL` / `get_default_kernel()`:全局单例。模块加载末尾(2207 行)只对它挂载领域插件。

## 7. 兼容门面

| 类 | 职责 |
|---|---|
| `IndustrialTermEngine` | 旧版翻译 API。`custom_dict` 最高优先;手动写入 `exact_phrases` 的非内置词条次之;其余委托 `kernel.translate_text` |
| `VarTableProcessor(mode, term_engine, kernel)` | `process_file` 解析 → 推导中文注释 → 翻译 → 清洗逗号 → 按平台导出,返回 `(序号, 变量名, 类型, 中文注释, 英文注释)` 列表;`process_directory` 批量处理 `.csv` / `.tsv`(跳过 `_new.csv`)并可生成 Markdown 报告 |
| `IOTableProcessor` | 同上,面向 IO 注释表,返回 `(地址, 原注释, 英文注释)` |
| `TableVerifier` | `verify_file` / `verify_directory`,封装 `Kernel.verify`,目录模式只处理源目录里的 `.csv` |

**方案 A / B**:B(默认)保持变量名不变、只翻译注释;A 同时把变量名译成英文并把空格替换为 `_`。

## 8. CLI

```
python core/plc_table_toolkit.py [--plugin FILE]... [--plugins-dir DIR] <命令> ...
  vars    --src-dir --dst-dir [--backup-cn] [--mode A|B] [--report] [--title]
  io      --src-dir --dst-dir [--backup-cn]
  verify  --src --target [--type var|io] [--mode A|B]   # 失败时退出码 1
  machine --machine-dir [--mode A|B]
```

`--plugin` / `--plugins-dir` 在子命令上用 `argparse.SUPPRESS` 作默认值,避免子解析器的默认值覆盖父级已解析的参数。`machine` 假定目录结构为 `io注释_备份_原始留档/变量表` → `变量表`,中文备份写到 `io注释_备份_规范中文版/变量表`,报告落在 `变量表/变量表中英文对照表_Corning交付版.md`。

## 9. 典型数据流

```
源文件 ──Kernel.parse──► TableDocument ──处理器逐行──► row.extra[new_en_c / new_cn_c]
                              │                              │
                  (按 priority 选解析器)        MultiStageTranslationEngine
                                                              │
         目标文件 ◄──Kernel.export (按 format_name 选导出器)◄──┘
             │
             └──► Kernel.verify(5 重断言 + PostVerifyRulePlugin)
```

## 10. 阅读中发现的行为与注意点

以下是阅读代码时注意到的,供决定是否处理时参考;标"已验证"的在本会话里跑过。

1. **单字词条造成中英混杂**(已验证):601 条词对里有大量单字(如 测→Measure、加→Add、全→All、刀→Cutter),整句没有精确命中时会被切碎替换,例如 `龘靐刀头` → `龘靐 Cutter Head`。`verify` 的"中文残留"检查能抓到未译字符,但抓不到这种半译输出。
2. **新建 `Kernel()` 不带领域插件**(已验证):只有 `get_default_kernel()` 会自动挂载修边机和光伏词典;自己 `Kernel()` 得到的是纯内置词典。
3. **`machine` 子命令只处理变量表**:不处理 IO 注释表;并且校验失败也不影响退出码(`verify` 子命令才会 `sys.exit(1)`)。
4. **`mode A` 下不检查变量名保真**:`Kernel.verify` 只在方案 B 下比较变量名。
5. **`IndustrialTermEngine.word_pairs` 是死属性**:修改它不会影响翻译(测试 `test_03` 已把这当作已知限制固定下来)。
6. **词对按长度而非优先级仲裁**:插件作者如果想用高优先级覆盖内置的短词条,需要提供同长度或更长的词条,或改用 `get_exact_phrases`。
7. **`PluginRegistry.register` 同 id 静默覆盖,且吞掉 `on_load` 异常**:插件 id 冲突或初始化失败不会有任何提示。
8. **`verify` 每个文件最多报告一个列级错误**(遇到即 `break`),修完再验可能冒出下一个。
9. **意大利语路径是非正式扩展点**:`get_exact_phrases_italian` 不在 SPI 抽象类里,靠 `hasattr` 探测。
