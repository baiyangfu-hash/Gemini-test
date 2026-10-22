# -*- coding: utf-8 -*-
"""
Tests for single-character-fallback diagnostics (translate_detailed / review_items).

Sample text uses rare glyphs and a private dictionary plugin so the assertions do not
depend on what the built-in dictionary happens to contain.
Zero external dependencies: standard library `unittest` only.
"""

import os
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_DIR = os.path.dirname(TESTS_DIR)
for p in [os.path.join(WORKFLOW_DIR, "core"), WORKFLOW_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from plc_table_toolkit import (
    DictionaryProviderPlugin,
    IndustrialTermEngine,
    IOTableProcessor,
    Kernel,
    VarTableProcessor,
    format_review_summary,
)


class _ReviewDictionary(DictionaryProviderPlugin):
    plugin_id = "review_test_dictionary"
    priority = 10

    def get_exact_phrases(self):
        return {"龘靐整句": "Exact Sentence"}

    def get_word_pairs(self):
        return [("龘", "Dragon"), ("靐靐", "Thunder"), ("鱻", "")]

    def get_regex_rules(self):
        return [(r"^槑(\d+)(.+)$", lambda m, tr: f"Rule {m.group(1)} {tr(m.group(2))}")]


def _kernel() -> Kernel:
    k = Kernel()
    k.register_plugin(_ReviewDictionary())
    return k


class TestTranslateDetailed(unittest.TestCase):

    def test_result_matches_translate_for_every_path(self):
        k = _kernel()
        engine = IndustrialTermEngine(custom_dict={"龘靐自定义": "Custom Entry"}, kernel=k)
        for text in ["龘靐整句", "龘靐自定义", "槑7龘", "龘靐靐", "龘", "plain ascii", "", "未知字符龘"]:
            with self.subTest(text=text):
                self.assertEqual(engine.translate_detailed(text)[0], engine.translate(text))
                self.assertEqual(k.translate_detailed(text)[0], k.translate_text(text))

    def test_single_char_fallback_is_reported(self):
        res, chars = _kernel().translate_detailed("靐靐")
        self.assertEqual((res, chars), ("Thunder", []))  # 多字词条覆盖，不算回退

        res, chars = _kernel().translate_detailed("龘靐靐")
        self.assertEqual((res, chars), ("Dragon Thunder", ["龘"]))  # 只有未被多字词条覆盖的单字才算

        res, chars = _kernel().translate_detailed("龘")
        self.assertEqual(res, "Dragon")
        self.assertEqual(chars, ["龘"])

    def test_exact_and_custom_dict_hits_have_no_fallback(self):
        k = _kernel()
        self.assertEqual(k.translate_detailed("龘靐整句"), ("Exact Sentence", []))
        engine = IndustrialTermEngine(custom_dict={"龘": "Mine"}, kernel=k)
        self.assertEqual(engine.translate_detailed("龘"), ("Mine", []))

    def test_empty_replacement_is_not_flagged(self):
        _, chars = _kernel().translate_detailed("鱻鱻")
        self.assertEqual(chars, [])

    def test_regex_handler_recursion_propagates_trace(self):
        res, chars = _kernel().translate_detailed("槑3龘")
        self.assertEqual(res, "Rule 3 Dragon")
        self.assertEqual(chars, ["龘"])

    def test_chars_are_deduplicated_in_order(self):
        _, chars = _kernel().translate_detailed("龘龘")
        self.assertEqual(chars, ["龘"])


class TestProcessorsCollectReviewItems(unittest.TestCase):

    def _write_gvl(self, path: str, comments):
        header = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
        rows = "".join(f"{i},Var{i},BOOL,False,False,False,False,{c},,\r\n" for i, c in enumerate(comments, 1))
        with open(path, "wb") as f:
            f.write((header + rows).encode("gbk"))

    def test_var_processor_records_only_fallback_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "a_变量表.csv")
            self._write_gvl(src, ["龘靐整句", "龘", "plain"])
            proc = VarTableProcessor(mode="B", kernel=_kernel())
            records = proc.process_file(src, os.path.join(tmp, "out", "a_变量表.csv"))

            self.assertEqual(len(records), 3)
            self.assertEqual([it["var"] for it in proc.review_items], ["Var2"])
            item = proc.review_items[0]
            self.assertEqual((item["file"], item["source"], item["english"], item["chars"]),
                             ("a_变量表.csv", "龘", "Dragon", ["龘"]))

    def test_process_directory_resets_items_and_prints_summary(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = os.path.join(tmp, "src")
            os.makedirs(src_dir)
            self._write_gvl(os.path.join(src_dir, "a_变量表.csv"), ["龘"])
            proc = VarTableProcessor(mode="B", kernel=_kernel())
            proc.review_items.append({"stale": True})

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                proc.process_directory(src_dir, os.path.join(tmp, "out"))
            self.assertEqual(len(proc.review_items), 1)
            self.assertNotIn("stale", proc.review_items[0])
            self.assertIn("[Review] 1 行", buf.getvalue())

            report = os.path.join(tmp, "review.md")
            proc.write_review_report(report)
            with open(report, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("共 **1** 行", text)
            self.assertIn("Dragon", text)

    def test_output_file_is_unchanged_by_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "a_变量表.csv")
            self._write_gvl(src, ["龘靐整句", "龘"])
            k = _kernel()
            dst = os.path.join(tmp, "out.csv")
            VarTableProcessor(mode="B", kernel=k).process_file(src, dst)
            with open(dst, "rb") as f:
                out = f.read().decode("gbk")
            self.assertIn("Exact Sentence", out)
            self.assertIn("Dragon", out)

    def test_io_processor_records_review_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "io注释.csv")
            with open(src, "wb") as f:
                f.write("软元件,注释\r\nX0,龘\r\nX1,龘靐整句\r\n".encode("gbk"))
            proc = IOTableProcessor(kernel=_kernel())
            proc.process_file(src, os.path.join(tmp, "out", "io注释.csv"))
            self.assertEqual([(it["var"], it["english"]) for it in proc.review_items], [("X0", "Dragon")])

    def test_summary_is_empty_without_items_and_truncates(self):
        self.assertEqual(format_review_summary([]), [])
        items = [{"file": "f", "no": str(i), "var": "v", "source": "龘", "english": "Dragon", "chars": ["龘"]}
                 for i in range(12)]
        lines = format_review_summary(items, limit=10)
        self.assertEqual(len(lines), 1 + 10 + 1)
        self.assertIn("另有 2 行", lines[-1])

    def test_legacy_term_engine_without_translate_detailed_still_works(self):
        class LegacyEngine:
            def translate(self, text, target_lang="en"):
                return "EN:" + text

            def derive_chinese_comment(self, var_name, existing_comment):
                return existing_comment

        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "a_变量表.csv")
            self._write_gvl(src, ["龘"])
            proc = VarTableProcessor(mode="B", term_engine=LegacyEngine(), kernel=_kernel())
            records = proc.process_file(src, os.path.join(tmp, "out.csv"))
            self.assertEqual(records[0][4], "EN:龘")
            self.assertEqual(proc.review_items, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
