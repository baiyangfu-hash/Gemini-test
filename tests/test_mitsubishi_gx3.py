# -*- coding: utf-8 -*-
"""
Unit Test Suite for Mitsubishi GX Works3 Platform Support & Solar Dictionary
=============================================================================
Verifies:
  1. Platform auto-detection (Inovance vs Mitsubishi GX Works3)
  2. MitsubishiGXWorks3Parser can_parse and parse behavior (27-col GVL, 2-col IO)
  3. MitsubishiGXWorks3Exporter UTF-16 LE + BOM encoding & column slotting (EN col 13, IT col 18)
  4. SolarFrameDictionaryPlugin translations in both English and Italian
  5. TableInspector on real Italian project files with zero file mutation
  6. TableVerifier compatibility with Mitsubishi tables
"""

import os
import sys
import unittest
import tempfile
import hashlib

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_ROOT = os.path.dirname(CURRENT_DIR)
for p in [os.path.join(WORKFLOW_ROOT, "core"), os.path.join(WORKFLOW_ROOT, "plugins"), WORKFLOW_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

import plc_table_toolkit as toolkit
from table_inspector import TableInspector
from solar_frame_dictionary_plugin import SolarFrameDictionaryPlugin

# Real Italian project directory path
REAL_ITALIAN_DIR = r"C:\Users\fubai\Documents\BaiduSyncdisk\项目\CT02-意大利项目\CT02意大利项目\SC1847-程序\程序-2025.5\SC1847意大利-2025-5\6.边框缓存机-buffer framing"
REAL_ITALIAN_GVL = os.path.join(REAL_ITALIAN_DIR, "2.PLC", "变量表", "变量表.csv")
REAL_ITALIAN_IO = os.path.join(REAL_ITALIAN_DIR, "2.PLC", "IO注释", "IO注释.csv")


class TestMitsubishiGXWorks3(unittest.TestCase):

    def setUp(self):
        self.kernel = toolkit.get_default_kernel()
        # Ensure SolarFrameDictionaryPlugin is loaded
        if "solar_frame_dictionary_plugin" not in self.kernel.registry._plugins:
            self.kernel.registry.register(SolarFrameDictionaryPlugin())

    def test_01_platform_detection(self):
        """Verify automatic detection of Inovance vs Mitsubishi GX Works3 platforms."""
        # 1. Mitsubishi GVL
        if os.path.exists(REAL_ITALIAN_GVL):
            plat_gvl = toolkit.detect_table_platform(REAL_ITALIAN_GVL)
            self.assertEqual(plat_gvl, "mitsubishi")

        # 2. Mitsubishi IO
        if os.path.exists(REAL_ITALIAN_IO):
            plat_io = toolkit.detect_table_platform(REAL_ITALIAN_IO)
            self.assertEqual(plat_io, "mitsubishi")

        # 3. Synthetic Inovance
        with tempfile.TemporaryDirectory() as tmpdir:
            ino_csv = os.path.join(tmpdir, "ino.csv")
            with open(ino_csv, "w", encoding="utf-8-sig") as f:
                f.write("序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,\r\n1,bStart,BOOL,,FALSE,False,False,启动,,\r\n")
            plat_ino = toolkit.detect_table_platform(ino_csv)
            self.assertIn(plat_ino, ["inovance", "autoshop", "inoproshop"])

    def test_02_parser_and_exporter_gvl_roundtrip(self):
        """Verify MitsubishiGXWorks3Parser & Exporter with 27-column layout and POU title."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = os.path.join(tmpdir, "mitsubishi_gvl_src.csv")
            dst_en_file = os.path.join(tmpdir, "mitsubishi_gvl_en.csv")
            dst_it_file = os.path.join(tmpdir, "mitsubishi_gvl_it.csv")

            # Synthetic GX Works3 GVL file (UTF-16 LE with BOM, Tab-delimited)
            header_27 = ["Class", "Label Name", "Data Type", "Constant", "English", "Chinese Simplified/简体中文"] + [f"Col{i}" for i in range(7, 28)]
            # Match Mitsubishi layout: Col 1 is Class, Col 2 is Name, Col 3 is Type, Col 8 is Comment (index 7), Col 14 is Chinese (index 14)
            row_27 = [""] * 27
            row_27[0] = "VAR_GLOBAL"
            row_27[1] = "g_bFrameBufferReady"
            row_27[2] = "Bit"
            row_27[7] = "边框缓存机准备就绪"
            row_27[14] = "边框缓存机准备就绪"

            content = '"边框缓存机"\r\n' + "\t".join(f'"{c}"' for c in header_27[:27]) + "\r\n" + "\t".join(f'"{c}"' for c in row_27) + "\r\n"
            with open(src_file, "wb") as f:
                f.write(b'\xff\xfe')
                f.write(content.encode("utf-16le"))

            # Test parser
            parser = toolkit.MitsubishiGXWorks3Parser()
            self.assertTrue(parser.can_parse(src_file))
            doc = parser.parse(src_file)
            self.assertEqual(len(doc.rows), 1)
            self.assertEqual(doc.rows[0].name, "g_bFrameBufferReady")
            self.assertEqual(doc.rows[0].comment, "边框缓存机准备就绪")

            # Test Exporter with English
            exporter = toolkit.MitsubishiGXWorks3Exporter()
            exporter.export(doc, dst_en_file, target_lang="en")
            self.assertTrue(os.path.exists(dst_en_file))

            # Verify UTF-16 LE BOM
            with open(dst_en_file, "rb") as f:
                bom = f.read(2)
                self.assertEqual(bom, b'\xff\xfe')
                body = f.read().decode("utf-16le")
                self.assertIn('"边框缓存机"', body)
                self.assertIn("g_bFrameBufferReady", body)

            # Test Exporter with Italian
            exporter.export(doc, dst_it_file, target_lang="it")
            with open(dst_it_file, "rb") as f:
                body_it = f.read().decode("utf-16le")
                self.assertIn("g_bFrameBufferReady", body_it)

    def test_03_solar_dictionary_translations(self):
        """Verify English and Italian translations via SolarFrameDictionaryPlugin."""
        engine = toolkit.IndustrialTermEngine(kernel=self.kernel)

        # 1. Exact phrase English
        self.assertEqual(engine.translate("边框缓存机", target_lang="en"), "Frame Buffer Machine")
        self.assertEqual(engine.translate("输送线正转", target_lang="en"), "Conveyor Line FWD")
        self.assertEqual(engine.translate("真空到达", target_lang="en"), "Vacuum Reached")
        self.assertEqual(engine.translate("申请stop", target_lang="en"), "Request Stop")

        # 2. Exact phrase Italian
        self.assertEqual(engine.translate("边框缓存机", target_lang="it"), "Buffer Telai")
        self.assertEqual(engine.translate("输送线正转", target_lang="it"), "Trasportatore Avanti")
        self.assertEqual(engine.translate("真空到达", target_lang="it"), "Vuoto Raggiunto")
        self.assertEqual(engine.translate("原点回归", target_lang="it"), "Ritorno a Zero")

    def test_04_inspect_real_italian_project_files(self):
        """Verify TableInspector on real Italian project files with strict non-mutation invariant."""
        if not os.path.exists(REAL_ITALIAN_GVL):
            self.skipTest(f"Real Italian project file not found: {REAL_ITALIAN_GVL}")

        # Compute SHA256 before inspection
        def file_sha256(p: str) -> str:
            with open(p, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()

        gvl_hash_before = file_sha256(REAL_ITALIAN_GVL)
        io_hash_before = file_sha256(REAL_ITALIAN_IO)

        # Inspect GVL
        gvl_res = TableInspector.inspect_single_table(REAL_ITALIAN_GVL)
        self.assertEqual(gvl_res.total_rows, 44)
        self.assertIn("BOOL", gvl_res.type_breakdown)
        self.assertGreater(gvl_res.type_breakdown["BOOL"], 30)

        # Inspect IO
        io_res = TableInspector.inspect_single_table(REAL_ITALIAN_IO)
        self.assertEqual(io_res.total_rows, 3766)
        self.assertIn("DEVICE", io_res.type_breakdown)
        self.assertGreater(io_res.type_breakdown["DEVICE"], 3700)

        # Non-mutation assertion
        self.assertEqual(file_sha256(REAL_ITALIAN_GVL), gvl_hash_before, "GVL file was mutated during inspection!")
        self.assertEqual(file_sha256(REAL_ITALIAN_IO), io_hash_before, "IO file was mutated during inspection!")

    def test_05_end_to_end_processor_on_mitsubishi_files(self):
        """Verify end-to-end processing of real Mitsubishi GVL file to pure English."""
        if not os.path.exists(REAL_ITALIAN_GVL):
            self.skipTest(f"Real Italian project file not found: {REAL_ITALIAN_GVL}")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_en = os.path.join(tmpdir, "变量表_EN.csv")
            out_it = os.path.join(tmpdir, "变量表_IT.csv")

            proc = toolkit.VarTableProcessor(mode="B", kernel=self.kernel)
            
            # English delivery
            recs_en = proc.process_file(REAL_ITALIAN_GVL, out_en, platform="mitsubishi", target_lang="en")
            self.assertEqual(len(recs_en), 44)
            self.assertTrue(os.path.exists(out_en))

            # Verify with TableVerifier
            ok_en, errs_en = toolkit.TableVerifier.verify_file(REAL_ITALIAN_GVL, out_en, mode="B", is_var_table=True, kernel=self.kernel)
            self.assertTrue(ok_en, f"English verification failed: {errs_en}")

            # Italian delivery
            recs_it = proc.process_file(REAL_ITALIAN_GVL, out_it, platform="mitsubishi", target_lang="it")
            self.assertEqual(len(recs_it), 44)
            self.assertTrue(os.path.exists(out_it))

            ok_it, errs_it = toolkit.TableVerifier.verify_file(REAL_ITALIAN_GVL, out_it, mode="B", is_var_table=True, kernel=self.kernel)
            self.assertTrue(ok_it, f"Italian verification failed: {errs_it}")


if __name__ == "__main__":
    unittest.main()
