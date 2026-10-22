# -*- coding: utf-8 -*-
"""
Unit Test Suite for TableInspector Domain Service
================================================
Verifies:
  1. Token parsing and 9-column InoProShop compatibility
  2. Data type preservation (BOOL, REAL, DINT, ARRAY, custom structs)
  3. Diff and translation status determination (translated, derived, unchanged, alert)
  4. Non-mutation file invariant (byte-for-byte SHA256 integrity before & after)
  5. Real workload discovery on Machine 3 (3-修边机)
"""

import os
import sys
import hashlib
import unittest
import tempfile

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_ROOT = os.path.dirname(CURRENT_DIR)
for p in [os.path.join(WORKFLOW_ROOT, "core"), os.path.join(WORKFLOW_ROOT, "plugins"), WORKFLOW_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

from table_inspector import TableInspector, VariableInspectionRecord, TableInspectionResult


class TestTableInspector(unittest.TestCase):

    def test_01_token_parsing(self):
        """Verify 9-column token extraction from standard GVL CSV lines."""
        sample_line = "1,bTrimmerHomeDone,BOOL,,FALSE,False,False,修边刀回原点完成,,"
        no, name, dtype, init_val, comment = TableInspector._parse_row_tokens(sample_line)
        self.assertEqual(no, "1")
        self.assertEqual(name, "bTrimmerHomeDone")
        self.assertEqual(dtype, "BOOL")
        self.assertEqual(init_val, "FALSE")
        self.assertEqual(comment, "修边刀回原点完成")

    def test_02_synthetic_diff_and_type_detection(self):
        """Verify alignment, type breakdown, and diff classification on synthetic data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_csv = os.path.join(tmpdir, "src.csv")
            dst_csv = os.path.join(tmpdir, "dst.csv")

            src_content = (
                "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
                "1,bStart,BOOL,,FALSE,False,False,启动按钮,,\r\n"
                "2,diCount,DINT,,0,False,False,工件计数,,\r\n"
                "3,修边气缸伸出,BOOL,,FALSE,False,False,,,\r\n"
                "4,stAxis,ST_CutterAxis,,,,,,,\r\n"
            )
            dst_content = (
                "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n"
                "1,bStart,BOOL,,FALSE,False,False,Start Button,,\r\n"
                "2,diCount,DINT,,0,False,False,Workpiece Count,,\r\n"
                "3,修边气缸伸出,BOOL,,FALSE,False,False,Trimming Cylinder Extend,,\r\n"
                "4,stAxis,ST_CutterAxis,,,,,,,\r\n"
            )

            with open(src_csv, "w", encoding="gbk", newline="") as f:
                f.write(src_content)
            with open(dst_csv, "w", encoding="gbk", newline="") as f:
                f.write(dst_content)

            res = TableInspector.inspect_single_table(src_csv, dst_csv)
            self.assertEqual(res.total_rows, 4)
            self.assertFalse(res.has_chinese_residue)
            self.assertEqual(res.residue_count, 0)

            # Check type breakdown
            self.assertEqual(res.type_breakdown.get("BOOL"), 2)
            self.assertEqual(res.type_breakdown.get("DINT"), 1)
            self.assertEqual(res.type_breakdown.get("STRUCT/DUT"), 1)

            # Check status classification
            recs = res.records
            self.assertEqual(recs[0].status, "translated")
            self.assertTrue(recs[0].is_diff)
            self.assertEqual(recs[1].status, "translated")
            self.assertEqual(recs[2].status, "derived") # was empty, derived
            self.assertEqual(recs[3].status, "unchanged")

    def test_03_zero_mutation_file_hash_invariant(self):
        """CRITICAL: Assert file SHA256 is 100% byte-for-byte identical before and after inspection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_file.csv")
            content = "序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n1,bTest,BOOL,,FALSE,False,False,测试注释,,\r\n"
            with open(test_file, "w", encoding="gbk", newline="") as f:
                f.write(content)

            with open(test_file, "rb") as f:
                hash_before = hashlib.sha256(f.read()).hexdigest()

            # Execute inspection multiple times
            for _ in range(5):
                res = TableInspector.inspect_single_table(test_file, test_file)
                self.assertEqual(len(res.records), 1)

            with open(test_file, "rb") as f:
                hash_after = hashlib.sha256(f.read()).hexdigest()
            self.assertEqual(hash_before, hash_after, "Table inspection MUST NOT mutate files!")

    def test_04_real_workload_machine_3(self):
        """Verify inspection on real Corning Machine 3 benchmark variable tables."""
        m3_dir = os.path.join(WORKFLOW_ROOT, "..", "康宁", "3-修边机")
        if not os.path.exists(m3_dir):
            self.skipTest(f"Machine 3 path not found: {m3_dir}")

        tables = TableInspector.list_machine_available_tables(m3_dir)
        self.assertGreaterEqual(len(tables), 12, "Should discover at least 12 benchmark tables")

        # Test inspecting 产量_变量表.csv
        file_item = next((t for t in tables if "产量" in t["file_name"]), None)
        self.assertIsNotNone(file_item)
        self.assertTrue(os.path.exists(file_item["src_path"]))
        self.assertTrue(os.path.exists(file_item["target_path"]))

        res = TableInspector.inspect_single_table(file_item["src_path"], file_item["target_path"])
        self.assertGreater(res.total_rows, 100)
        self.assertIn("BOOL", res.type_breakdown)
        self.assertIn("DINT", res.type_breakdown)
        self.assertFalse(res.has_chinese_residue) # Delivery must have 0 residue!
        self.assertEqual(res.residue_count, 0)

    def test_05_discover_machines(self):
        """Verify dynamic machine auto-discovery scans workspace directories correctly."""
        ws_root = os.path.abspath(os.path.join(WORKFLOW_ROOT, ".."))
        corning_dir = os.path.join(ws_root, "康宁")
        if not os.path.isdir(corning_dir):
            self.skipTest(f"Corning workspace not found: {corning_dir}")
        machines = TableInspector.discover_machines(ws_root)
        self.assertGreaterEqual(len(machines), 3, "Should discover at least 3 Corning machines dynamically")
        names = [m["name"] for m in machines]
        self.assertTrue(any("3-修边机" in n for n in names))
        self.assertTrue(any("2-撕胶带机" in n for n in names))
        self.assertTrue(any("1-封边机" in n for n in names))


if __name__ == "__main__":
    unittest.main()
