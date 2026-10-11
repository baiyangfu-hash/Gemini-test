# -*- coding: utf-8 -*-
"""
=============================================================================
Machine 3 (3-修边机) One-Click Delivery & 100% Quality Verification Script
=============================================================================
This script executes the complete delivery pipeline for Corning Machine 3:
  1. Loads microkernel and registers TrimmerDictionaryPlugin (priority 10).
  2. Batch processes the 12 benchmark variable tables from:
       康宁\3-修边机\io注释_备份_原始留档\变量表\
     into:
       Normalized Chinese: 康宁\3-修边机\io注释_备份_规范中文版\变量表\
       Pure English:       康宁\3-修边机\变量表\
  3. Generates the consolidated bilingual Markdown table:
       康宁\3-修边机\变量表\变量表中英文对照表_Corning交付版.md
     with interactive TOC, summary statistics, and anchors #section-1 to #section-12.
  4. Runs TableVerifier 5-fold assertions across all 12 files and outputs:
       FINAL RESULT: ALL 12 FILES PASSED 100% QUALITY CHECKS!
=============================================================================
"""

import os
import sys

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_ROOT = os.path.dirname(_CURRENT_DIR)
for p in [os.path.join(WORKFLOW_ROOT, "core"), os.path.join(WORKFLOW_ROOT, "plugins"), WORKFLOW_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

import plc_table_toolkit as ptt
from trimmer_dictionary_plugin import TrimmerDictionaryPlugin, register_trimmer_plugin

BENCHMARK_12_FILES = [
    "产量_变量表.csv",
    "伺服_变量表.csv",
    "修边刀使用统计_变量表.csv",
    "停机_变量表.csv",
    "准备_变量表.csv",
    "回原点_变量表.csv",
    "手动操作_变量表.csv",
    "报警_变量表.csv",
    "系统准备_变量表.csv",
    "自动_变量表.csv",
    "输送归正_变量表.csv",
    "配方_变量表.csv",
]


def run_delivery() -> bool:
    print("=" * 80)
    print("Corning Machine 3 (3-修边机) 12 Benchmark Variable Tables Delivery Pipeline")
    print("=" * 80)

    # 1. Initialize microkernel and register trimmer dictionary plugin
    kernel = ptt.get_default_kernel()
    trimmer_plugin = register_trimmer_plugin(kernel)
    print(f"[*] Registered domain plugin: [{trimmer_plugin.plugin_id}] (priority={trimmer_plugin.priority})")

    # 2. Setup paths
    base_proj_dir = os.path.dirname(WORKFLOW_ROOT)
    machine_dir = os.path.join(base_proj_dir, "康宁", "3-修边机")
    src_dir = os.path.join(machine_dir, "io注释_备份_原始留档", "变量表")
    dst_cn_dir = os.path.join(machine_dir, "io注释_备份_规范中文版", "变量表")
    dst_en_dir = os.path.join(machine_dir, "变量表")
    report_md_path = os.path.join(dst_en_dir, "变量表中英文对照表_Corning交付版.md")

    if not os.path.exists(src_dir):
        print(f"[ERROR] Source directory does not exist: {src_dir}")
        return False

    os.makedirs(dst_cn_dir, exist_ok=True)
    os.makedirs(dst_en_dir, exist_ok=True)

    # 3. Batch process the 12 CSV variable tables
    processor = ptt.VarTableProcessor(mode="B", kernel=kernel)
    project_title = "Corning Project CT173 - 3-修边机"
    print(f"\n[1/3] Processing 12 benchmark variable tables (Mode B)...")
    all_records = {}
    for fn in BENCHMARK_12_FILES:
        sp = os.path.join(src_dir, fn)
        dep = os.path.join(dst_en_dir, fn)
        dcp = os.path.join(dst_cn_dir, fn)
        rec = processor.process_file(sp, dep, dcp)
        all_records[fn] = rec
        print(f"  -> [OK] {fn:24s} | {len(rec):5d} rows")

    processor.generate_markdown_report(all_records, report_md_path, project_title)

    total_rows = sum(len(r) for r in all_records.values())
    print(f"\n[2/3] Batch processing complete: {len(all_records)} files, {total_rows} total data rows.")
    print(f"      Normalized Chinese backup: {dst_cn_dir}")
    print(f"      Pure English delivery:     {dst_en_dir}")
    print(f"      Consolidated Markdown:     {report_md_path}")

    # 4. Strict Quality Verification
    print(f"\n[3/3] Executing TableVerifier quality checks...")
    verifier = ptt.TableVerifier()
    passed = True
    for fn in BENCHMARK_12_FILES:
        sp = os.path.join(src_dir, fn)
        dep = os.path.join(dst_en_dir, fn)
        ok, errs = verifier.verify_file(sp, dep, mode="B", is_var_table=True, kernel=kernel)
        if ok:
            print(f"  [PASS] {fn:24s} | 100% Invariants Verified")
        else:
            passed = False
            print(f"  [FAIL] {fn:24s} | {errs}")

    if passed:
        print("\n" + "=" * 80)
        print("FINAL RESULT: ALL 12 FILES PASSED 100% QUALITY CHECKS!")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("FINAL RESULT: VERIFICATION FAILED!")
        print("=" * 80)

    return passed


if __name__ == "__main__":
    success = run_delivery()
    sys.exit(0 if success else 1)
