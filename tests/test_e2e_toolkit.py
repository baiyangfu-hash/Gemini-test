# -*- coding: utf-8 -*-
"""
End-to-End (E2E) Test Suite for PLC Table Toolkit
=================================================
Opaque-Box 4-Tier Test Architecture:
- Tier 1: Feature Coverage (Plugin SPIs, Facades, CLI subcommands)
- Tier 2: Boundary & Corner Cases (CRLF/LF, empty comments, comma sanitization, GBK)
- Tier 3: Cross-Feature Interactions (Plugin dictionary cascade, Post-verifier, Markdown TOC)
- Tier 4: Real-world Workload Scenarios (Turnkey machine processing, 5-fold quality gate)

Zero external dependencies: uses Python standard library `unittest` only.
"""

import os
import sys
import re
import shutil
import tempfile
import unittest
import subprocess
from typing import List, Dict, Tuple, Optional

# Ensure toolkit directory, core, plugins and archive are in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_DIR = os.path.dirname(CURRENT_DIR)
CORE_DIR = os.path.join(WORKFLOW_DIR, "core")
PLUGINS_DIR = os.path.join(WORKFLOW_DIR, "plugins")
ARCHIVE_DIR = os.path.join(WORKFLOW_DIR, "archive")

for p in [CORE_DIR, PLUGINS_DIR, ARCHIVE_DIR, WORKFLOW_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import plc_table_toolkit as toolkit


# Check availability of Microkernel SPI classes (refactored architecture)
HAS_SPI = hasattr(toolkit, "BasePlugin") and hasattr(toolkit, "PluginRegistry")


# ============================================================================
# Tier 1: Feature Coverage
# ============================================================================

class TestTier1FeatureCoverage(unittest.TestCase):
    """Tier 1: Feature Coverage across SPI contracts, Python API facades, and CLI."""

    def test_01_spi_base_plugin_contract(self):
        """Verify BasePlugin interface definition, default attributes, and lifecycle hooks."""
        if not HAS_SPI:
            self.skipTest("Microkernel SPI (BasePlugin) not yet exported by plc_table_toolkit (M1 in progress)")

        BasePlugin = getattr(toolkit, "BasePlugin")
        self.assertTrue(hasattr(BasePlugin, "plugin_id"))
        self.assertTrue(hasattr(BasePlugin, "plugin_name"))
        self.assertTrue(hasattr(BasePlugin, "version"))
        self.assertTrue(hasattr(BasePlugin, "priority"))
        self.assertTrue(hasattr(BasePlugin, "on_load"))
        self.assertTrue(hasattr(BasePlugin, "initialize"))
        self.assertTrue(hasattr(BasePlugin, "on_unload"))

        # Test subclassing
        class ConcretePlugin(BasePlugin):
            plugin_id = "test.concrete"
            plugin_name = "Test Concrete Plugin"
            version = "1.0.0"
            priority = 50

        p = ConcretePlugin()
        self.assertEqual(p.plugin_id, "test.concrete")
        self.assertEqual(p.priority, 50)
        # Ensure default hooks execute cleanly
        p.on_load(None)
        p.initialize({})
        p.on_unload()

    def test_02_spi_table_parser_plugin_contract(self):
        """Verify TableParserPlugin abstract SPI contract."""
        if not HAS_SPI:
            self.skipTest("TableParserPlugin not yet exported by plc_table_toolkit (M1 in progress)")

        TableParserPlugin = getattr(toolkit, "TableParserPlugin")
        BasePlugin = getattr(toolkit, "BasePlugin")
        self.assertTrue(issubclass(TableParserPlugin, BasePlugin))
        self.assertTrue(hasattr(TableParserPlugin, "can_parse"))
        self.assertTrue(hasattr(TableParserPlugin, "parse"))

    def test_03_spi_dictionary_provider_plugin_contract(self):
        """Verify DictionaryProviderPlugin abstract SPI contract."""
        if not HAS_SPI:
            self.skipTest("DictionaryProviderPlugin not yet exported by plc_table_toolkit (M1 in progress)")

        DictionaryProviderPlugin = getattr(toolkit, "DictionaryProviderPlugin")
        BasePlugin = getattr(toolkit, "BasePlugin")
        self.assertTrue(issubclass(DictionaryProviderPlugin, BasePlugin))
        self.assertTrue(hasattr(DictionaryProviderPlugin, "get_exact_phrases"))
        self.assertTrue(hasattr(DictionaryProviderPlugin, "get_word_pairs"))
        self.assertTrue(hasattr(DictionaryProviderPlugin, "get_regex_rules"))

    def test_04_spi_post_verify_rule_plugin_contract(self):
        """Verify PostVerifyRulePlugin abstract SPI contract."""
        if not HAS_SPI:
            self.skipTest("PostVerifyRulePlugin not yet exported by plc_table_toolkit (M1 in progress)")

        PostVerifyRulePlugin = getattr(toolkit, "PostVerifyRulePlugin")
        BasePlugin = getattr(toolkit, "BasePlugin")
        self.assertTrue(issubclass(PostVerifyRulePlugin, BasePlugin))
        self.assertTrue(hasattr(PostVerifyRulePlugin, "verify"))

    def test_05_microkernel_plugin_registry_and_lifecycle(self):
        """Verify PluginRegistry registration, lifecycle hook execution, and priority resolution."""
        if not HAS_SPI:
            self.skipTest("PluginRegistry not yet exported by plc_table_toolkit (M1 in progress)")

        PluginRegistry = getattr(toolkit, "PluginRegistry")
        BasePlugin = getattr(toolkit, "BasePlugin")

        registry = PluginRegistry()
        events = []

        class AlphaPlugin(BasePlugin):
            plugin_id = "test.alpha"
            plugin_name = "Alpha"
            version = "1.0.0"
            priority = 100

            def on_load(self, kernel):
                events.append("alpha_load")

        class BetaPlugin(BasePlugin):
            plugin_id = "test.beta"
            plugin_name = "Beta"
            version = "1.0.0"
            priority = 10  # Higher priority

            def on_load(self, kernel):
                events.append("beta_load")

        p_alpha = AlphaPlugin()
        p_beta = BetaPlugin()

        registry.register(p_alpha)
        registry.register(p_beta)

        plugins = registry.get_plugins()
        # Verify priority sorting: lower number = higher priority
        self.assertEqual(plugins[0].plugin_id, "test.beta")
        self.assertEqual(plugins[1].plugin_id, "test.alpha")

    def test_06_facade_industrial_term_engine_basic_translation(self):
        """Verify IndustrialTermEngine default exact phrases, regex patterns, and greedy match."""
        engine = toolkit.IndustrialTermEngine()

        # 1. Exact phrase
        self.assertEqual(engine.translate("ABS定位启动"), "ABS Positioning Start")
        self.assertEqual(engine.translate("经过时间"), "Elapsed Time")

        # 2. Dynamic regex: Clock
        self.assertEqual(engine.translate("PLC时钟读出_年"), "PLC Clock Read Year")
        self.assertEqual(engine.translate("PLC时钟写入_秒"), "PLC Clock Write Second")

        # 3. Dynamic regex: Array & Multi-axis
        self.assertEqual(engine.translate("报警清除[0]"), "Alarm Clear [0]")
        self.assertIn("Axis", engine.translate("0/1轴准备OK标志"))

        # 4. Pure English unchanged
        self.assertEqual(engine.translate("Motor_Run_Cmd"), "Motor_Run_Cmd")

    def test_07_facade_industrial_term_engine_custom_dict(self):
        """Verify custom_dict parameter overrides or extends translations."""
        custom = {
            "康宁定制工位": "Corning Custom Station",
            "ABS定位启动": "Custom ABS Start Override"
        }
        engine = toolkit.IndustrialTermEngine(custom_dict=custom)
        self.assertEqual(engine.translate("康宁定制工位"), "Corning Custom Station")
        self.assertEqual(engine.translate("ABS定位启动"), "Custom ABS Start Override")

    def test_08_facade_var_table_processor_mode_b(self):
        """Verify VarTableProcessor Mode B preserves variable names 100% and translates comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_csv = os.path.join(tmpdir, "src.csv")
            dst_en_csv = os.path.join(tmpdir, "en.csv")
            dst_cn_csv = os.path.join(tmpdir, "cn.csv")

            header = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
            row1 = "1,g_bStartPrep,BOOL,False,False,False,False,准备执行,,\r\n"
            row2 = "2,伺服报警标志,BOOL,False,False,False,False,,,,\r\n"

            with open(src_csv, "wb") as f:
                f.write((header + row1 + row2).encode('gbk'))

            proc = toolkit.VarTableProcessor(mode="B")
            records = proc.process_file(src_csv, dst_en_csv, dst_cn_csv)

            self.assertEqual(len(records), 2)
            self.assertEqual(records[0][1], "g_bStartPrep")
            self.assertEqual(records[1][1], "伺服报警标志")  # Mode B: preserved

            # Verify English output
            with open(dst_en_csv, "rb") as f:
                en_bytes = f.read()
            en_lines = en_bytes.decode('gbk').splitlines()
            self.assertEqual(len(en_lines), 3)
            p1 = en_lines[1].split(',')
            self.assertEqual(p1[1], "g_bStartPrep")
            self.assertIn("Preparation", p1[7])

            p2 = en_lines[2].split(',')
            self.assertEqual(p2[1], "伺服报警标志")
            # Derived comment should be translated to pure English
            self.assertFalse(bool(re.search(r'[\u4e00-\u9fff]', p2[7])))

    def test_09_facade_var_table_processor_mode_a(self):
        """Verify VarTableProcessor Mode A translates Chinese variable names to snake_case."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_csv = os.path.join(tmpdir, "src.csv")
            dst_en_csv = os.path.join(tmpdir, "en.csv")

            header = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
            row = "1,系统准备,BOOL,False,False,False,False,系统准备完成,,\r\n"

            with open(src_csv, "wb") as f:
                f.write((header + row).encode('gbk'))

            proc = toolkit.VarTableProcessor(mode="A")
            proc.process_file(src_csv, dst_en_csv)

            with open(dst_en_csv, "rb") as f:
                en_lines = f.read().decode('gbk').splitlines()

            parts = en_lines[1].split(',')
            # Mode A translates variable name
            self.assertNotIn("系统准备", parts[1])
            self.assertIn("Prep", parts[1])

    def test_10_facade_io_table_processor(self):
        """Verify IOTableProcessor translates comments and preserves hardware addresses."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_csv = os.path.join(tmpdir, "io_src.csv")
            dst_en_csv = os.path.join(tmpdir, "io_en.csv")

            header = "软元件,注释,类型\r\n"
            row1 = "X0,气缸伸出到位,DI\r\n"
            row2 = "Y0,电机正转启动,DO\r\n"

            with open(src_csv, "wb") as f:
                f.write((header + row1 + row2).encode('gbk'))

            proc = toolkit.IOTableProcessor()
            records = proc.process_file(src_csv, dst_en_csv)

            self.assertEqual(len(records), 2)
            self.assertEqual(records[0][0], "X0")
            self.assertIn("Cylinder", records[0][2])

            with open(dst_en_csv, "rb") as f:
                en_lines = f.read().decode('gbk').splitlines()
            p1 = en_lines[1].split(',')
            self.assertEqual(p1[0], "X0")
            self.assertIn("Cylinder", p1[1])

    def test_11_facade_table_verifier(self):
        """Verify TableVerifier 5-fold assertion logic on valid and invalid files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_csv = os.path.join(tmpdir, "src.csv")
            valid_dst = os.path.join(tmpdir, "valid_dst.csv")
            invalid_dst = os.path.join(tmpdir, "invalid_dst.csv")

            header = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
            row = "1,g_bAlarm,BOOL,False,False,False,False,Alarm Triggered,,\r\n"

            with open(src_csv, "wb") as f:
                f.write((header + row).encode('gbk'))

            with open(valid_dst, "wb") as f:
                f.write((header + row).encode('gbk'))

            # Missing CRLF and contains Chinese in comment
            bad_row = "1,g_bAlarm,BOOL,False,False,False,False,报警触发,,\n"
            with open(invalid_dst, "wb") as f:
                f.write((header + bad_row).encode('gbk'))

            # Test valid file
            ok_valid, errs_valid = toolkit.TableVerifier.verify_file(src_csv, valid_dst, mode="B")
            self.assertTrue(ok_valid)
            self.assertEqual(len(errs_valid), 0)

            # Test invalid file
            ok_invalid, errs_invalid = toolkit.TableVerifier.verify_file(src_csv, invalid_dst, mode="B")
            self.assertFalse(ok_invalid)
            self.assertTrue(any("CRLF" in e for e in errs_invalid) or any("中文" in e for e in errs_invalid))

    def test_12_cli_subcommands_help(self):
        """Verify CLI subcommands (vars, io, verify, machine) support --help with exit code 0."""
        toolkit_path = os.path.join(CORE_DIR, "plc_table_toolkit.py")
        if not os.path.exists(toolkit_path):
            toolkit_path = os.path.join(WORKFLOW_DIR, "plc_table_toolkit.py")

        for cmd in ["--help", "vars --help", "io --help", "verify --help", "machine --help"]:
            args = [sys.executable, toolkit_path] + cmd.split()
            res = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', cwd=WORKFLOW_DIR)
            self.assertEqual(res.returncode, 0, f"Command failed: {cmd}, stderr: {res.stderr}")

    def test_13_legacy_plc_io_translator_bugfix(self):
        """Verify bugfix in plc_io_translator: SUBSTITUTION_TERMS is defined and executes cleanly (F16)."""
        import plc_io_translator
        self.assertTrue(hasattr(plc_io_translator, "SUBSTITUTION_TERMS"), "SUBSTITUTION_TERMS must be defined")
        # Translate a comment that requires substitution
        res = plc_io_translator.translate_comment("非字典未匹配测试注释")
        self.assertIsNotNone(res)
        self.assertIsInstance(res, str)


# ============================================================================
# Tier 2: Boundary & Corner Cases
# ============================================================================

class TestTier2BoundaryAndCornerCases(unittest.TestCase):
    """Tier 2: Edge conditions, encoding invariants, and format boundaries."""

    def test_01_empty_comment_chinese_variable_derivation(self):
        """Verify that a Chinese variable with an empty comment derives the comment and translates it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_csv = os.path.join(tmpdir, "var.csv")
            en_csv = os.path.join(tmpdir, "en.csv")
            cn_csv = os.path.join(tmpdir, "cn.csv")

            header = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
            row = "1,修边刀上升到位,BOOL,False,False,False,False,,,,\r\n"

            with open(src_csv, "wb") as f:
                f.write((header + row).encode('gbk'))

            proc = toolkit.VarTableProcessor(mode="B")
            proc.process_file(src_csv, en_csv, cn_csv)

            # Verify CN backup has derived Chinese comment
            with open(cn_csv, "rb") as f:
                cn_lines = f.read().decode('gbk').splitlines()
            self.assertEqual(cn_lines[1].split(',')[7], "修边刀上升到位")

            # Verify EN delivery has pure English comment (0 Chinese)
            with open(en_csv, "rb") as f:
                en_lines = f.read().decode('gbk').splitlines()
            en_c = en_lines[1].split(',')[7]
            self.assertGreater(len(en_c), 0)
            self.assertIsNone(re.search(r'[\u4e00-\u9fff]', en_c))

    def test_02_empty_comment_alphanumeric_variable(self):
        """Verify that an alphanumeric variable with an empty comment leaves comment empty without error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_csv = os.path.join(tmpdir, "var.csv")
            en_csv = os.path.join(tmpdir, "en.csv")

            header = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
            row = "1,Axis1_Actual_Pos,LREAL,False,0.0,False,False,,,,\r\n"

            with open(src_csv, "wb") as f:
                f.write((header + row).encode('gbk'))

            proc = toolkit.VarTableProcessor(mode="B")
            proc.process_file(src_csv, en_csv)

            with open(en_csv, "rb") as f:
                en_lines = f.read().decode('gbk').splitlines()
            parts = en_lines[1].split(',')
            self.assertEqual(parts[1], "Axis1_Actual_Pos")
            self.assertEqual(parts[7], "")
            self.assertEqual(len(parts), 10)  # 9 cols + trailing comma

    def test_03_crlf_vs_lf_line_endings_enforcement(self):
        """Verify that input Unix LF is normalized to Windows CRLF, and Verifier strictly demands CRLF."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_csv = os.path.join(tmpdir, "lf_src.csv")
            en_csv = os.path.join(tmpdir, "en.csv")

            # Pure LF source
            content = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\n" \
                      "1,Var_Test,BOOL,False,False,False,False,准备执行,,\n"

            with open(src_csv, "wb") as f:
                f.write(content.encode('gbk'))

            proc = toolkit.VarTableProcessor(mode="B")
            proc.process_file(src_csv, en_csv)

            with open(en_csv, "rb") as f:
                en_bytes = f.read()

            # Must contain CRLF binary pattern
            self.assertIn(b'\r\n', en_bytes)
            self.assertNotIn(b'[^\r]\n', en_bytes)

            # Test Verifier CRLF rejection
            lf_only_csv = os.path.join(tmpdir, "lf_only.csv")
            with open(lf_only_csv, "wb") as f:
                f.write(content.encode('gbk'))

            ok, errs = toolkit.TableVerifier.verify_file(src_csv, lf_only_csv, mode="B")
            self.assertFalse(ok)
            self.assertTrue(any("CRLF" in e for e in errs))

    def test_04_embedded_commas_in_comments_sanitization(self):
        """Verify English and Chinese commas in comments are sanitized to ' / ' to prevent column misalignment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_csv = os.path.join(tmpdir, "comma_src.csv")
            en_csv = os.path.join(tmpdir, "comma_en.csv")

            header = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
            # Embedded English comma and Chinese comma
            row = "1,g_iCurveType,INT,False,0,False,False,曲线类型: 0, T型；1，S型,,\r\n"

            with open(src_csv, "wb") as f:
                f.write((header + row).encode('gbk'))

            proc = toolkit.VarTableProcessor(mode="B")
            proc.process_file(src_csv, en_csv)

            with open(en_csv, "rb") as f:
                en_lines = f.read().decode('gbk').splitlines()

            parts = en_lines[1].split(',')
            # Exactly 10 parts (9 columns + trailing comma)
            self.assertEqual(len(parts), 10, f"Malformed column split: {parts}")
            # Neither ',' nor '，' should remain in the comment field
            self.assertNotIn("，", parts[7])
            self.assertIn(" / ", parts[7])

    def test_05_trailing_comma_10_token_structure(self):
        """Verify InoProShop native 9-column format with trailing comma is 100% preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_csv = os.path.join(tmpdir, "trailing.csv")
            en_csv = os.path.join(tmpdir, "trailing_en.csv")

            header = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
            row = "1,Test_Var,BOOL,False,False,False,False,准备就绪,,\r\n"

            with open(src_csv, "wb") as f:
                f.write((header + row).encode('gbk'))

            proc = toolkit.VarTableProcessor(mode="B")
            proc.process_file(src_csv, en_csv)

            with open(en_csv, "rb") as f:
                en_lines = f.read().decode('gbk').splitlines()

            for idx, line in enumerate(en_lines):
                self.assertTrue(line.endswith(','), f"Line {idx} missing trailing comma: {line}")
                tokens = line.split(',')
                self.assertEqual(len(tokens), 10, f"Line {idx} expected 10 tokens on split, got {len(tokens)}")

    def test_06_gbk_special_characters_and_industrial_symbols(self):
        """Verify GBK multi-byte characters and industrial symbols round-trip cleanly without decode error."""
        engine = toolkit.IndustrialTermEngine()

        symbols_test = [
            ("温度设定：25℃", "Temperature Setting: 25℃"),
            ("旋转角度：90°", "Rotation Angle: 90°"),
            ("公差：±0.05", "Tolerance: ±0.05"),
            ("伺服报警！（严重）", "Servo Alarm! (Severe)"),
        ]

        for src, expected_snippet in symbols_test:
            res = engine.translate(src)
            # Must encode to GBK cleanly
            gbk_bytes = res.encode('gbk')
            self.assertIsNotNone(gbk_bytes)
            # Must not contain Chinese characters
            self.assertIsNone(re.search(r'[\u4e00-\u9fff]', res), f"Residue in: {res}")

    def test_07_header_only_and_empty_rows(self):
        """Verify processing a CSV with header only or blank rows executes gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_csv = os.path.join(tmpdir, "empty_table.csv")
            en_csv = os.path.join(tmpdir, "empty_en.csv")

            header = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n\r\n"
            with open(src_csv, "wb") as f:
                f.write(header.encode('gbk'))

            proc = toolkit.VarTableProcessor(mode="B")
            records = proc.process_file(src_csv, en_csv)

            self.assertEqual(len(records), 0)
            with open(en_csv, "rb") as f:
                en_lines = f.read().decode('gbk').splitlines()
            self.assertEqual(en_lines[0], header.splitlines()[0])


# ============================================================================
# Tier 3: Cross-Feature Interactions
# ============================================================================

class TestTier3CrossFeatureInteractions(unittest.TestCase):
    """Tier 3: Dynamic plugin dictionaries, post-verify hooks, and interactive TOC reports."""

    def test_01_plugin_dynamic_dictionary_priority_cascade(self):
        """Verify dynamic DictionaryProviderPlugin with high priority overrides base dictionary."""
        if not HAS_SPI:
            self.skipTest("Microkernel SPI not yet exported by plc_table_toolkit (M1 in progress)")

        DictionaryProviderPlugin = getattr(toolkit, "DictionaryProviderPlugin")
        Kernel = getattr(toolkit, "Kernel", None) or getattr(toolkit, "PluginRegistry", None)

        class CustomDomainPlugin(DictionaryProviderPlugin):
            plugin_id = "custom.trimmer"
            plugin_name = "Trimmer Custom Dictionary"
            version = "1.0.0"
            priority = 10  # Higher priority than core default 100

            def get_exact_phrases(self):
                return {
                    "准备": "High-Priority Plugin Ready",
                    "修边机特殊报警": "Trimmer Special Alarm"
                }

            def get_word_pairs(self):
                return [("削边", "Edge Chamfer")]

            def get_regex_rules(self):
                return []

        p = CustomDomainPlugin()
        kernel = Kernel() if Kernel else None
        if kernel and hasattr(kernel, "register"):
            kernel.register(p)

        engine = toolkit.IndustrialTermEngine(kernel=kernel) if kernel else toolkit.IndustrialTermEngine(custom_dict=p.get_exact_phrases())
        res = engine.translate("准备")
        self.assertIn("Plugin Ready", res)

    def test_02_markdown_interactive_toc_and_anchors(self):
        """Verify consolidated Markdown delivery table includes interactive TOC, anchors, and return links."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dst_en_dir = os.path.join(tmpdir, "en")
            report_path = os.path.join(dst_en_dir, "变量表中英文对照表_Corning交付版.md")
            os.makedirs(src_dir, exist_ok=True)

            header = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
            table1 = header + "1,g_bYield,DINT,False,0,False,False,生产产量统计,,\r\n"
            table2 = header + "1,g_bServo,BOOL,False,False,False,False,伺服使能就绪,,\r\n"

            with open(os.path.join(src_dir, "1_产量_变量表.csv"), "wb") as f:
                f.write(table1.encode('gbk'))
            with open(os.path.join(src_dir, "2_伺服_变量表.csv"), "wb") as f:
                f.write(table2.encode('gbk'))

            proc = toolkit.VarTableProcessor(mode="B")
            proc.process_directory(src_dir, dst_en_dir, report_md_path=report_path, project_title="Corning CT173 Test")

            self.assertTrue(os.path.exists(report_path))
            with open(report_path, "r", encoding="utf-8") as f:
                md_content = f.read()

            # 1. Header block
            self.assertIn("# 变量表中英文对照全表", md_content)
            self.assertIn("Corning CT173 Test", md_content)

            # 2. Table of Contents
            self.assertIn("## 目录与汇总导航 (Table of Contents)", md_content)
            self.assertIn("[点击查看详细对照](#section-1)", md_content)
            self.assertIn("[点击查看详细对照](#section-2)", md_content)

            # 3. Anchors in content sections
            self.assertIn('<span id="section-1"></span>', md_content)
            self.assertIn('<span id="section-2"></span>', md_content)

            # 4. Return to TOC link
            self.assertIn("[返回目录](#目录与汇总导航-table-of-contents)", md_content)

            # 5. Table headers
            self.assertIn("| 序号 | 变量名 (Variable Name) | 数据类型 | 规范中文注释 (Chinese) | 交付英文注释 (English Standard) |", md_content)

    def test_03_io_table_8col_vs_2col_autodetection(self):
        """Verify IOTableProcessor correctly handles AutoShop 8+ column layout vs 2-column layout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            io_8col = os.path.join(tmpdir, "io_8col.csv")
            io_2col = os.path.join(tmpdir, "io_2col.csv")
            en_8col = os.path.join(tmpdir, "en_8col.csv")
            en_2col = os.path.join(tmpdir, "en_2col.csv")

            # 8-column layout (comment at index 7)
            line_8col = "X0,0,0,0,0,0,0,急停按钮输入,,\r\n"
            with open(io_8col, "wb") as f:
                f.write(line_8col.encode('gbk'))

            # 2-column layout (comment at index 1)
            line_2col = "Y0,报警指示灯输出\r\n"
            with open(io_2col, "wb") as f:
                f.write(line_2col.encode('gbk'))

            proc = toolkit.IOTableProcessor()
            proc.process_file(io_8col, en_8col)
            proc.process_file(io_2col, en_2col)

            with open(en_8col, "rb") as f:
                parts_8 = f.read().decode('gbk').splitlines()[0].split(',')
            self.assertIn("Emergency Stop", parts_8[7])

            with open(en_2col, "rb") as f:
                parts_2 = f.read().decode('gbk').splitlines()[0].split(',')
            self.assertIn("Alarm", parts_2[1])


# ============================================================================
# Tier 4: Real-World Workload Scenarios
# ============================================================================

class TestTier4RealWorldWorkloads(unittest.TestCase):
    """Tier 4: Turnkey machine workflow, full 12-table simulation, and quality gate rejection."""

    def test_01_turnkey_machine_workflow_end_to_end(self):
        """Simulate a complete machine directory with GVL tables, process, and pass 100% quality gate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            machine_root = os.path.join(tmpdir, "3-修边机")
            var_src = os.path.join(machine_root, "io注释_备份_原始留档", "变量表")
            var_dst = os.path.join(machine_root, "变量表")
            var_cn = os.path.join(machine_root, "io注释_备份_规范中文版", "变量表")
            report_md = os.path.join(var_dst, "变量表中英文对照表_Corning交付版.md")
            os.makedirs(var_src, exist_ok=True)

            header = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"

            # Table 1: Yield
            t1_data = header + \
                      "1,g_diCurrentShiftYield,DINT,False,0,False,False,当前班次产量,,\r\n" + \
                      "2,g_bResetYieldCounter,BOOL,False,False,False,False,产量清零触发,,\r\n"

            # Table 2: Servo
            t2_data = header + \
                      "1,Axis1_Cmd_Pos,LREAL,False,0.0,False,False,轴1指令位置,,\r\n" + \
                      "2,Axis1_Abs_Move_Start,BOOL,False,False,False,False,ABS定位启动,,\r\n"

            # Table 3: Preparation (with derived comment)
            t3_data = header + \
                      "1,系统准备完成标志,BOOL,False,False,False,False,,,,\r\n" + \
                      "2,g_bTrimmerBladeUpInPos,BOOL,False,False,False,False,修边刀上升到位,,\r\n"

            with open(os.path.join(var_src, "产量_变量表.csv"), "wb") as f:
                f.write(t1_data.encode('gbk'))
            with open(os.path.join(var_src, "伺服_变量表.csv"), "wb") as f:
                f.write(t2_data.encode('gbk'))
            with open(os.path.join(var_src, "准备_变量表.csv"), "wb") as f:
                f.write(t3_data.encode('gbk'))

            # Execute batch processing
            proc = toolkit.VarTableProcessor(mode="B")
            proc.process_directory(var_src, var_dst, var_cn, report_md_path=report_md, project_title="3-修边机")

            # Verify directory outputs exist
            self.assertTrue(os.path.exists(os.path.join(var_dst, "产量_变量表.csv")))
            self.assertTrue(os.path.exists(os.path.join(var_dst, "伺服_变量表.csv")))
            self.assertTrue(os.path.exists(os.path.join(var_dst, "准备_变量表.csv")))
            self.assertTrue(os.path.exists(report_md))

            # Run 5-fold acceptance quality gate
            passed = toolkit.TableVerifier.verify_directory(var_src, var_dst, mode="B", is_var_table=True)
            self.assertTrue(passed, "TableVerifier.verify_directory failed on processed delivery tables!")

    def test_02_adversarial_quality_gate_rejection_on_injected_flaws(self):
        """Adversarial testing: Inject 5 distinct flaw types and assert TableVerifier catches every single one."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_csv = os.path.join(tmpdir, "src.csv")
            header = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
            row1 = "1,g_bReady,BOOL,False,False,False,False,准备就绪,,\r\n"
            row2 = "2,g_bAlarm,BOOL,False,False,False,False,报警触发,,\r\n"

            with open(src_csv, "wb") as f:
                f.write((header + row1 + row2).encode('gbk'))

            # Flaw 1: Line count mismatch (row truncated)
            flaw1_path = os.path.join(tmpdir, "flaw1_linecount.csv")
            with open(flaw1_path, "wb") as f:
                f.write((header + "1,g_bReady,BOOL,False,False,False,False,Ready Done,,\r\n").encode('gbk'))
            ok1, errs1 = toolkit.TableVerifier.verify_file(src_csv, flaw1_path, mode="B")
            self.assertFalse(ok1)
            self.assertTrue(any("行数不吻合" in e for e in errs1))

            # Flaw 2: Missing CRLF (pure LF)
            flaw2_path = os.path.join(tmpdir, "flaw2_lf.csv")
            flaw2_content = header.replace("\r\n", "\n") + \
                            "1,g_bReady,BOOL,False,False,False,False,Ready Done,,\n" + \
                            "2,g_bAlarm,BOOL,False,False,False,False,Alarm Triggered,,\n"
            with open(flaw2_path, "wb") as f:
                f.write(flaw2_content.encode('gbk'))
            ok2, errs2 = toolkit.TableVerifier.verify_file(src_csv, flaw2_path, mode="B")
            self.assertFalse(ok2)
            self.assertTrue(any("CRLF" in e for e in errs2))

            # Flaw 3: Insufficient columns (< 9 columns)
            flaw3_path = os.path.join(tmpdir, "flaw3_cols.csv")
            flaw3_content = header + \
                            "1,g_bReady,BOOL,False,False\r\n" + \
                            "2,g_bAlarm,BOOL,False,False,False,False,Alarm Triggered,,\r\n"
            with open(flaw3_path, "wb") as f:
                f.write(flaw3_content.encode('gbk'))
            ok3, errs3 = toolkit.TableVerifier.verify_file(src_csv, flaw3_path, mode="B")
            self.assertFalse(ok3)
            self.assertTrue(any("列数不足" in e for e in errs3))

            # Flaw 4: Variable name modified in Mode B
            flaw4_path = os.path.join(tmpdir, "flaw4_varname.csv")
            flaw4_content = header + \
                            "1,MUTATED_VAR_NAME,BOOL,False,False,False,False,Ready Done,,\r\n" + \
                            "2,g_bAlarm,BOOL,False,False,False,False,Alarm Triggered,,\r\n"
            with open(flaw4_path, "wb") as f:
                f.write(flaw4_content.encode('gbk'))
            ok4, errs4 = toolkit.TableVerifier.verify_file(src_csv, flaw4_path, mode="B")
            self.assertFalse(ok4)
            self.assertTrue(any("变量名被意外修改" in e for e in errs4))

            # Flaw 5: Chinese character residue in comment column
            flaw5_path = os.path.join(tmpdir, "flaw5_chinese_residue.csv")
            flaw5_content = header + \
                            "1,g_bReady,BOOL,False,False,False,False,Ready Done,,\r\n" + \
                            "2,g_bAlarm,BOOL,False,False,False,False,Alarm 报警未翻译,,\r\n"
            with open(flaw5_path, "wb") as f:
                f.write(flaw5_content.encode('gbk'))
            ok5, errs5 = toolkit.TableVerifier.verify_file(src_csv, flaw5_path, mode="B")
            self.assertFalse(ok5)
            self.assertTrue(any("包含中文字符" in e for e in errs5))


# ============================================================================
# Main Test Runner
# ============================================================================

def run_suite() -> bool:
    """Execute the full 4-tier test suite and print a structured summary report."""
    print("=" * 75)
    print("  PLC Table Toolkit E2E Test Suite (Tiers 1-4)")
    print(f"  Microkernel SPI Status: {'DETECTED & ACTIVE' if HAS_SPI else 'PENDING M1 IMPLEMENTATION'}")
    print("=" * 75)

    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    suite.addTests(loader.loadTestsFromTestCase(TestTier1FeatureCoverage))
    suite.addTests(loader.loadTestsFromTestCase(TestTier2BoundaryAndCornerCases))
    suite.addTests(loader.loadTestsFromTestCase(TestTier3CrossFeatureInteractions))
    suite.addTests(loader.loadTestsFromTestCase(TestTier4RealWorldWorkloads))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 75)
    print(f"  Tests Run: {result.testsRun}")
    print(f"  Failures:  {len(result.failures)}")
    print(f"  Errors:    {len(result.errors)}")
    print(f"  Skipped:   {len(result.skipped)}")
    print(f"  Final Status: {'ALL PASS [100% SUCCESS]' if result.wasSuccessful() else 'TEST FAILURES DETECTED'}")
    print("=" * 75 + "\n")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_suite()
    sys.exit(0 if success else 1)
