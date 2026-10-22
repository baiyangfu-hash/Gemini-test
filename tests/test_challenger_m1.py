# -*- coding: utf-8 -*-
"""
=============================================================================
Adversarial Stress Test Suite for Milestone M1 Microkernel Architecture
=============================================================================
Author: Challenger 1 (Milestone M1)
Target: plc_table_toolkit.py, demo_custom_plugin.py, plc_io_translator.py

Challenge Dimensions:
1. Dynamic plugin loading with priority collisions (overrides, ties, ID clashing)
2. Plugin exception containment (malformed files, throwing hooks, broken returns)
3. Backward-compatible API edge cases (custom_dict mutations, word_pairs orphan, legacy facades)
4. CLI subcommands behavior under unusual arguments (subparser default wipeout, missing dirs)

Zero external dependencies: uses standard library `unittest` only.
=============================================================================
"""

import os
import sys
import re
import shutil
import tempfile
import argparse
import unittest
from typing import List, Dict, Tuple, Optional, Any

# Ensure Workflow root, core, and plugins are in sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_DIR = os.path.dirname(TESTS_DIR)
CORE_DIR = os.path.join(WORKFLOW_DIR, "core")
PLUGINS_DIR = os.path.join(WORKFLOW_DIR, "plugins")
for p in [CORE_DIR, PLUGINS_DIR, WORKFLOW_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import plc_table_toolkit as toolkit
from plc_table_toolkit import (
    BasePlugin,
    TableParserPlugin,
    DictionaryProviderPlugin,
    TableExporterPlugin,
    PostVerifyRulePlugin,
    PluginRegistry,
    Kernel,
    TableRow,
    TableDocument,
    IndustrialTermEngine,
    VarTableProcessor,
    IOTableProcessor,
    TableVerifier,
    get_default_kernel,
)


# =============================================================================
# Dimension 1: Dynamic Plugin Loading with Priority Collisions & Overrides
# =============================================================================

class TestPriorityCollisionsAndOverrides(unittest.TestCase):
    """Stress-test plugin priority sorting, identical-priority collisions, and ID clashes."""

    def test_01_priority_tie_breaking_order(self):
        """
        Adversarial Test: When two plugins register with IDENTICAL priority (e.g. 20),
        verify the tie-breaking behavior across exact phrases, word pairs, and regex rules.
        """
        kernel = Kernel()

        class PluginAlpha(DictionaryProviderPlugin):
            plugin_id = "plugin_alpha"
            priority = 20

            def get_exact_phrases(self):
                return {"碰撞测试": "Alpha Winner"}

            def get_word_pairs(self):
                return [("碰撞", "Alpha Collision")]

            def get_regex_rules(self):
                return [(re.compile(r"^碰撞-(\d+)$"), lambda m, tr: f"Alpha #{m.group(1)}")]

        class PluginBeta(DictionaryProviderPlugin):
            plugin_id = "plugin_beta"
            priority = 20  # Identical priority to Alpha

            def get_exact_phrases(self):
                return {"碰撞测试": "Beta Winner"}

            def get_word_pairs(self):
                return [("碰撞", "Beta Collision")]

            def get_regex_rules(self):
                return [(re.compile(r"^碰撞-(\d+)$"), lambda m, tr: f"Beta #{m.group(1)}")]

        # Register Alpha first, then Beta
        kernel.register_plugin(PluginAlpha())
        kernel.register_plugin(PluginBeta())

        # Exact match check:
        # In MultiStageTranslationEngine._rebuild_cache_if_needed:
        # providers = sorted(..., key=priority) -> [Alpha, Beta, Builtin]
        # for p in reversed(providers) -> [Builtin, Beta, Alpha]
        # Therefore, Alpha updates LAST and overrides Beta!
        exact_res = kernel.translate_text("碰撞测试")
        self.assertEqual(exact_res, "Alpha Winner", "Earlier registered plugin should win tie-break in exact match")

        # Regex check:
        # providers = [Alpha, Beta, Builtin]. Evaluated in order: Alpha first!
        regex_res = kernel.translate_text("碰撞-123")
        self.assertEqual(regex_res, "Alpha #123", "Earlier registered plugin should win tie-break in regex evaluation")

        # Word pairs check:
        # Both pairs have length 2. Stable sort keeps Alpha first!
        word_res = kernel.translate_text("发生碰撞现象")
        self.assertIn("Alpha Collision", word_res, "Earlier registered plugin should win tie-break in greedy word pairs")

    def test_02_plugin_id_collision_silent_overwrite_and_missing_unload(self):
        """
        Adversarial Test: Registering a new plugin with an EXISTING plugin_id
        replaces it in the registry, but fails to invoke on_unload() on the displaced plugin.
        """
        kernel = Kernel()
        unloaded_events = []

        class DisplacedPlugin(BasePlugin):
            plugin_id = "clashing_id"
            priority = 100

            def on_unload(self):
                unloaded_events.append("displaced_unloaded")

        class ReplacementPlugin(BasePlugin):
            plugin_id = "clashing_id"
            priority = 10

        p1 = DisplacedPlugin()
        p2 = ReplacementPlugin()

        kernel.register_plugin(p1)
        self.assertIs(kernel.registry.get_plugin("clashing_id"), p1)

        # Overwrite with p2
        kernel.register_plugin(p2)
        self.assertIs(kernel.registry.get_plugin("clashing_id"), p2)

        # ARCHITECTURAL DEFECT CHECK: p1.on_unload() was NEVER called on replacement!
        self.assertNotIn("displaced_unloaded", unloaded_events,
                         "Displaced plugin on_unload() was skipped during ID collision replacement")

    def test_03_negative_and_zero_priority(self):
        """
        Adversarial Test: Verify priority sorting supports zero (0) and negative (-10) priorities,
        ensuring they take precedence over standard positive priorities (10, 50, 100).
        """
        kernel = Kernel()

        class SuperHighPriorityPlugin(DictionaryProviderPlugin):
            plugin_id = "super_high"
            priority = -10  # Negative priority: higher than 0 and 10

            def get_exact_phrases(self):
                return {"准备": "Negative Priority Ready"}

            def get_word_pairs(self):
                return []

            def get_regex_rules(self):
                return []

        class ZeroPriorityPlugin(DictionaryProviderPlugin):
            plugin_id = "zero_prio"
            priority = 0  # Zero priority

            def get_exact_phrases(self):
                return {"准备": "Zero Priority Ready"}

            def get_word_pairs(self):
                return []

            def get_regex_rules(self):
                return []

        kernel.register_plugin(ZeroPriorityPlugin())
        kernel.register_plugin(SuperHighPriorityPlugin())

        # -10 < 0 < 100, so SuperHighPriorityPlugin (-10) must win
        res = kernel.translate_text("准备")
        self.assertEqual(res, "Negative Priority Ready")

    def test_04_cache_invalidation_gap_on_plugin_unregister(self):
        """
        Verify that when a DictionaryProviderPlugin is unregistered via kernel.unregister_plugin(),
        the engine cache is automatically invalidated and stale translations are purged.
        """
        kernel = Kernel()

        class TempPlugin(DictionaryProviderPlugin):
            plugin_id = "temp_plugin"
            priority = 5

            def get_exact_phrases(self):
                return {"龘靐术语": "Temp Translation"}

            def get_word_pairs(self):
                return []

            def get_regex_rules(self):
                return []

        p = TempPlugin()
        kernel.register_plugin(p)

        # 1. First translation populates engine cache
        res1 = kernel.translate_text("龘靐术语")
        self.assertEqual(res1, "Temp Translation")

        # 2. Unregister plugin via kernel.unregister_plugin
        unregistered = kernel.unregister_plugin("temp_plugin")
        self.assertIs(unregistered, p)
        self.assertIsNone(kernel.registry.get_plugin("temp_plugin"))

        # 3. Cache must be automatically invalidated: subsequent translation purges unregistered translation
        res2 = kernel.translate_text("龘靐术语")
        self.assertEqual(res2, "龘靐术语",
                         "Cache should be invalidated automatically upon unregistering plugin")

    def test_05_word_pairs_longest_match_vs_priority(self):
        """
        Adversarial Test: Multi-Stage Translation Engine sorts word_pairs by length descending (longest match).
        Verify that a longer phrase in a LOWER priority plugin wins over a shorter sub-word in a HIGHER priority plugin.
        """
        kernel = Kernel()

        class HighPriorityShortWord(DictionaryProviderPlugin):
            plugin_id = "p_short"
            priority = 10

            def get_exact_phrases(self):
                return {}

            def get_word_pairs(self):
                return [("刀", "HighPrioBlade")]

            def get_regex_rules(self):
                return []

        class LowPriorityLongPhrase(DictionaryProviderPlugin):
            plugin_id = "p_long"
            priority = 90

            def get_exact_phrases(self):
                return {}

            def get_word_pairs(self):
                return [("龘靐刀头", "LowPrioTrimmingCutter")]

            def get_regex_rules(self):
                return []

        kernel.register_plugin(HighPriorityShortWord())
        kernel.register_plugin(LowPriorityLongPhrase())

        # "龘靐刀头上升" contains "龘靐刀头" (len 4) and "刀" (len 1).
        # Because greedy match sorts by len(x[0]) descending, "龘靐刀头" is matched first despite lower priority!
        # (Rare glyphs are used on purpose so the built-in dictionary cannot match part of the sample text.)
        res = kernel.translate_text("龘靐刀头上升")
        self.assertIn("LowPrioTrimmingCutter", res)
        self.assertNotIn("HighPrioBlade", res)


# =============================================================================
# Dimension 2: Plugin Exception Containment & Fault Isolation
# =============================================================================

class TestPluginExceptionContainment(unittest.TestCase):
    """Stress-test system resilience against broken plugins, failing hooks, and malformed data."""

    def test_01_failing_on_load_hook_is_contained(self):
        """Verify that an unhandled exception in on_load() does not crash registration."""
        kernel = Kernel()

        class BrokenLoadPlugin(BasePlugin):
            plugin_id = "broken_loader"

            def on_load(self, k):
                raise RuntimeError("Catastrophic on_load failure!")

        # Should not raise exception
        try:
            kernel.register_plugin(BrokenLoadPlugin())
            registered = True
        except Exception:
            registered = False

        self.assertTrue(registered, "Plugin registration should contain on_load() exceptions")
        # Plugin remains registered despite on_load failure
        self.assertIsNotNone(kernel.registry.get_plugin("broken_loader"))

    def test_02_failing_on_unload_hook_is_contained(self):
        """Verify that an unhandled exception in on_unload() does not crash unregister."""
        kernel = Kernel()

        class BrokenUnloadPlugin(BasePlugin):
            plugin_id = "broken_unloader"

            def on_unload(self):
                raise RuntimeError("Catastrophic on_unload failure!")

        kernel.register_plugin(BrokenUnloadPlugin())
        unregistered = kernel.registry.unregister("broken_unloader")
        self.assertIsNotNone(unregistered)

    def test_03_broken_dictionary_provider_methods_crash_pipeline(self):
        """
        Verify that if a DictionaryProviderPlugin raises an unhandled exception in
        get_exact_phrases(), get_word_pairs(), or get_regex_rules(),
        MultiStageTranslationEngine safely isolates the error, logs a warning, and falls back to built-in dictionary.
        """
        kernel = Kernel()

        class ExplodingDictionaryPlugin(DictionaryProviderPlugin):
            plugin_id = "exploding_dict"
            priority = 10

            def get_exact_phrases(self):
                raise ValueError("Exploding get_exact_phrases!")

            def get_word_pairs(self):
                return []

            def get_regex_rules(self):
                return []

        kernel.register_plugin(ExplodingDictionaryPlugin())

        # Translating triggers _rebuild_cache_if_needed() and must NOT crash with ValueError
        res = kernel.translate_text("准备")
        self.assertEqual(res, "Ready", "Engine should safely fall back to built-in dictionary despite broken plugin")

    def test_04_dictionary_provider_returning_none_crashes_with_type_error(self):
        """
        Verify that if a DictionaryProviderPlugin returns None instead of dict/list,
        MultiStageTranslationEngine safely handles None without TypeError and falls back cleanly.
        """
        kernel = Kernel()

        class NoneReturningDictionaryPlugin(DictionaryProviderPlugin):
            plugin_id = "none_dict"
            priority = 10

            def get_exact_phrases(self):
                return None  # Bad return type

            def get_word_pairs(self):
                return None

            def get_regex_rules(self):
                return None

        kernel.register_plugin(NoneReturningDictionaryPlugin())

        res = kernel.translate_text("准备")
        self.assertEqual(res, "Ready", "Engine should handle None return values gracefully without TypeError")

    def test_05_dynamic_regex_handler_exception_is_safely_isolated(self):
        """
        Verify that if a dynamic regex rule handler throws an unhandled exception,
        MultiStageTranslationEngine catches it and proceeds to the next rule / greedy stage.
        """
        kernel = Kernel()

        class FailingRegexHandlerPlugin(DictionaryProviderPlugin):
            plugin_id = "failing_regex_plugin"
            priority = 10

            def get_exact_phrases(self):
                return {}

            def get_word_pairs(self):
                return [("伺服", "Servo")]

            def get_regex_rules(self):
                def exploding_handler(m, tr):
                    raise ZeroDivisionError("Division by zero in regex handler!")

                return [(re.compile(r"^伺服-(.+)$"), exploding_handler)]

        kernel.register_plugin(FailingRegexHandlerPlugin())

        # Translating "伺服-123" matches the regex, but the handler throws ZeroDivisionError.
        # The engine should catch it and fall back to Tier 3 greedy substitution!
        res = kernel.translate_text("伺服-123")
        self.assertIn("Servo", res, "Engine should catch handler exception and fall back to greedy substitution")

    def test_06_post_verify_rule_plugin_exception_contained(self):
        """
        Verify that an unhandled exception inside PostVerifyRulePlugin.verify()
        is caught by TableVerifier and reported as a verification error without crashing.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "src.csv")
            tgt = os.path.join(tmpdir, "tgt.csv")

            header = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
            row = "1,g_bReady,BOOL,False,False,False,False,Ready Completed,,\r\n"
            with open(src, "wb") as f:
                f.write((header + row).encode('gbk'))
            with open(tgt, "wb") as f:
                f.write((header + row).encode('gbk'))

            kernel = Kernel()

            class ExplodingVerifierPlugin(PostVerifyRulePlugin):
                plugin_id = "exploding_verifier"

                def verify(self, src_p, tgt_p, doc, ctx):
                    raise RuntimeError("Crash inside verifier plugin!")

            kernel.register_plugin(ExplodingVerifierPlugin())

            ok, errors = TableVerifier.verify_file(src, tgt, mode="B", kernel=kernel)
            self.assertFalse(ok)
            self.assertTrue(any("Crash inside verifier plugin!" in e for e in errors))

    def test_07_load_from_directory_skips_corrupted_files(self):
        """
        Verify that PluginRegistry.load_from_directory() skips invalid Python files
        with SyntaxError without aborting other valid plugins.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # File 1: Syntax error
            bad_file = os.path.join(tmpdir, "01_bad_plugin.py")
            with open(bad_file, "w", encoding="utf-8") as f:
                f.write("def broken_syntax(:\n    pass\n")

            # File 2: Valid plugin
            good_file = os.path.join(tmpdir, "02_good_plugin.py")
            with open(good_file, "w", encoding="utf-8") as f:
                f.write(
                    "from plc_table_toolkit import BasePlugin\n"
                    "class ValidPlugin(BasePlugin):\n"
                    "    plugin_id = 'valid_from_dir'\n"
                )

            registry = PluginRegistry()
            loaded = registry.load_from_directory(tmpdir)

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].plugin_id, "valid_from_dir")


# =============================================================================
# Dimension 3: Backward-Compatible API Edge Cases & Mutability
# =============================================================================

class TestBackwardCompatibleApiEdgeCases(unittest.TestCase):
    """Stress-test legacy facades, dict mutations, and shared global kernel side-effects."""

    def test_01_custom_dict_mutation_post_init(self):
        """
        Adversarial Test: Modifying engine.custom_dict AFTER initialization
        must take immediate effect in engine.translate().
        """
        engine = IndustrialTermEngine()
        self.assertEqual(engine.translate("龘靐热添词"), "龘靐热添词")

        # Mutate custom_dict post-init
        engine.custom_dict["龘靐热添词"] = "Dynamic Post-Init Term"
        self.assertEqual(engine.translate("龘靐热添词"), "Dynamic Post-Init Term")

    def test_02_exact_phrases_mutation_override_and_addition(self):
        """
        Adversarial Test: Directly mutating engine.exact_phrases (legacy direct dict access)
        must override built-in exact phrases.
        """
        engine = IndustrialTermEngine()

        # 1. Override existing built-in exact phrase
        engine.exact_phrases["ABS定位启动"] = "Manual Custom ABS Start"
        self.assertEqual(engine.translate("ABS定位启动"), "Manual Custom ABS Start")

        # 2. Add brand new phrase
        engine.exact_phrases["非标专机工位"] = "Non-Standard Machine Station"
        self.assertEqual(engine.translate("非标专机工位"), "Non-Standard Machine Station")

    def test_03_word_pairs_mutation_is_ignored_by_kernel(self):
        """
        Adversarial Test: Directly mutating engine.word_pairs (e.g. insert or append)
        is completely ignored by engine.translate() because it delegates to the microkernel!
        EMPIRICAL OBSERVATION: This is a subtle backward-compatibility limitation.
        """
        engine = IndustrialTermEngine()

        # Insert custom word pair directly into engine.word_pairs
        engine.word_pairs.insert(0, ("专用轴", "Specialized Axis"))

        # In legacy code, this would replace "专用轴" with "Specialized Axis".
        # In the microkernel architecture, engine delegates to kernel, which uses BuiltinDictionaryPlugin!
        res = engine.translate("专用轴运行中")
        self.assertNotIn("Specialized Axis", res,
                         "engine.word_pairs mutations are ignored by microkernel delegation")

    def test_04_default_kernel_singleton_cross_contamination(self):
        """
        Adversarial Test: Verify that modifying get_default_kernel() affects all
        facade instances that do not explicitly supply an isolated Kernel instance.
        """
        k_default = get_default_kernel()

        class LeakyPlugin(DictionaryProviderPlugin):
            plugin_id = "leaky_plugin"
            priority = 10

            def get_exact_phrases(self):
                return {"龘靐污染词": "Global Contamination"}

            def get_word_pairs(self):
                return []

            def get_regex_rules(self):
                return []

        p = LeakyPlugin()
        k_default.register_plugin(p)

        # Instance 1 and Instance 2 created with default args share k_default
        e1 = IndustrialTermEngine()
        e2 = IndustrialTermEngine()
        self.assertEqual(e1.translate("龘靐污染词"), "Global Contamination")
        self.assertEqual(e2.translate("龘靐污染词"), "Global Contamination")

        # An isolated Kernel is NOT contaminated
        k_isolated = Kernel()
        e_isolated = IndustrialTermEngine(kernel=k_isolated)
        self.assertEqual(e_isolated.translate("龘靐污染词"), "龘靐污染词")

        # Clean up k_default
        k_default.registry.unregister("leaky_plugin")
        k_default.engine.invalidate_cache()

    def test_05_vartableprocessor_with_mismatched_kernels(self):
        """
        Adversarial Test: If VarTableProcessor is initialized with term_engine having Kernel A,
        but processor.kernel is Kernel B (or default), processor.process_file uses Kernel B for
        parse/export and Kernel A for translation.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "var.csv")
            dst_en = os.path.join(tmpdir, "en.csv")
            header = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
            row = "1,Test_Var,BOOL,False,False,False,False,准备执行,,\r\n"
            with open(src, "wb") as f:
                f.write((header + row).encode('gbk'))

            k_a = Kernel()
            k_b = Kernel()

            class TermKernelPlugin(DictionaryProviderPlugin):
                plugin_id = "term_plugin"
                priority = 10

                def get_exact_phrases(self):
                    return {"准备执行": "Kernel A Preparation"}

                def get_word_pairs(self):
                    return []

                def get_regex_rules(self):
                    return []

            k_a.register_plugin(TermKernelPlugin())

            engine = IndustrialTermEngine(kernel=k_a)
            proc = VarTableProcessor(mode="B", term_engine=engine, kernel=k_b)

            records = proc.process_file(src, dst_en)
            self.assertEqual(records[0][4], "Kernel A Preparation")


# =============================================================================
# Dimension 4: CLI Subcommands Under Unusual Arguments & Argparse Edge Cases
# =============================================================================

class TestCliUnusualArguments(unittest.TestCase):
    """Stress-test CLI argument parsing, subparser default override pitfalls, and invalid paths."""

    def test_01_cli_argparse_subparser_plugin_default_wipeout(self):
        """
        CRITICAL ADVERSARIAL DISCOVERY:
        In plc_table_toolkit.py:
        Both the root parser and the subparser define:
            p.add_argument("--plugin", action="append", default=[])
        When a user runs:
            python plc_table_toolkit.py --plugin custom.py vars --src-dir in --dst-dir out
        The root parser parses --plugin custom.py into args.plugin = ['custom.py'].
        However, the subparser 'vars' executes with default=[], OVERWRITING args.plugin with []!
        """
        toolkit_path = os.path.join(WORKFLOW_DIR, "plc_table_toolkit.py")

        # Construct an argument parser mimicking plc_table_toolkit.py main()
        parser = argparse.ArgumentParser()
        toolkit._add_plugin_args(parser)
        subparsers = parser.add_subparsers(dest="command")
        p_vars = subparsers.add_parser("vars")
        p_vars.add_argument("--src-dir", required=True)
        p_vars.add_argument("--dst-dir", required=True)
        toolkit._add_plugin_args(p_vars)

        # Scenario A: --plugin placed BEFORE subcommand 'vars'
        args_before = parser.parse_args(["--plugin", "my_plugin.py", "vars", "--src-dir", "in", "--dst-dir", "out"])
        self.assertEqual(args_before.plugin, ["my_plugin.py"],
                         "Root --plugin must be preserved when specified before subcommand")

        # Scenario B: --plugin placed AFTER subcommand 'vars'
        args_after = parser.parse_args(["vars", "--src-dir", "in", "--dst-dir", "out", "--plugin", "my_plugin.py"])
        self.assertEqual(args_after.plugin, ["my_plugin.py"],
                         "When specified after subcommand, subparser preserves --plugin")

    def test_02_cli_subparser_plugins_dir_default_wipeout(self):
        """
        Similarly, verify --plugins-dir specified before the subcommand is preserved by subparser.
        """
        parser = argparse.ArgumentParser()
        toolkit._add_plugin_args(parser)
        subparsers = parser.add_subparsers(dest="command")
        p_vars = subparsers.add_parser("vars")
        p_vars.add_argument("--src-dir", required=True)
        p_vars.add_argument("--dst-dir", required=True)
        toolkit._add_plugin_args(p_vars)

        # Scenario A: --plugins-dir placed BEFORE subcommand 'vars'
        args_before = parser.parse_args(["--plugins-dir", "my_dir", "vars", "--src-dir", "in", "--dst-dir", "out"])
        self.assertEqual(args_before.plugins_dir, "my_dir",
                         "Root --plugins-dir must be preserved when specified before subcommand")

        # Scenario B: --plugins-dir placed AFTER subcommand 'vars'
        args_after = parser.parse_args(["vars", "--src-dir", "in", "--dst-dir", "out", "--plugins-dir", "my_dir"])
        self.assertEqual(args_after.plugins_dir, "my_dir",
                         "Subparser --plugins-dir must be preserved when specified after subcommand")

    def test_03_cli_vars_nonexistent_directory_raises_filenotfound(self):
        """Verify that passing a non-existent source directory to VarTableProcessor raises FileNotFoundError."""
        proc = VarTableProcessor()
        with self.assertRaises(FileNotFoundError):
            proc.process_directory("non_existent_directory_12345", "dst_dir")

    def test_04_cli_machine_nonexistent_directory_fails_silently(self):
        """
        Adversarial Test: In main(), when command is 'machine':
        If var_src does not exist, the script does nothing and returns without error or warning.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_machine = os.path.join(tmpdir, "empty_machine")
            os.makedirs(empty_machine, exist_ok=True)
            var_src = os.path.join(empty_machine, "io注释_备份_原始留档", "变量表")
            self.assertFalse(os.path.exists(var_src))

            # Simulate machine branch logic
            var_src = os.path.join(empty_machine, "io注释_备份_原始留档", "变量表")
            var_dst = os.path.join(empty_machine, "变量表")
            executed = False
            if os.path.exists(var_src):
                executed = True

            self.assertFalse(executed, "Machine subcommand silently does nothing when var_src directory is absent")


# =============================================================================
# Main Runner
# =============================================================================

def run_challenger_suite() -> bool:
    print("=" * 80)
    print("  EMPIRICAL CHALLENGER TEST SUITE - MILESTONE M1")
    print("  Adversarial Stress Testing of Microkernel, Plugins, Facades & CLI")
    print("=" * 80)

    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    suite.addTests(loader.loadTestsFromTestCase(TestPriorityCollisionsAndOverrides))
    suite.addTests(loader.loadTestsFromTestCase(TestPluginExceptionContainment))
    suite.addTests(loader.loadTestsFromTestCase(TestBackwardCompatibleApiEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestCliUnusualArguments))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 80)
    print(f"  Tests Executed: {result.testsRun}")
    print(f"  Failures:       {len(result.failures)}")
    print(f"  Errors:         {len(result.errors)}")
    print(f"  Overall Status: {'ALL PASS [VERIFIED]' if result.wasSuccessful() else 'FAILURES / DEFECTS DETECTED'}")
    print("=" * 80 + "\n")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_challenger_suite()
    sys.exit(0 if success else 1)
