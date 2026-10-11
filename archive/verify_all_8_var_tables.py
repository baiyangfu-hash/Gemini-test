# -*- coding: utf-8 -*-
import os, sys, re

sys.stdout.reconfigure(encoding='utf-8')

orig_dir = r"c:\Users\fubai\Documents\BaiduSyncdisk\项目\CT173-美国康宁-6月-付白杨\PLC+HMI程序\康宁\1-封边机\io注释_备份_原始留档\变量表"
en_dir = r"c:\Users\fubai\Documents\BaiduSyncdisk\项目\CT173-美国康宁-6月-付白杨\PLC+HMI程序\康宁\1-封边机\变量表"

all_files = [
    "安全继电器_变量表.csv",
    "报警_变量表.csv",
    "变量表.csv",
    "产量_变量表.csv",
    "手动变量表.csv",
    "轴控制变量表.csv",
    "准备变量表.csv",
    "自动变量表.csv"
]

all_passed = True
print("================ FULL VERIFICATION SUITE: ALL 8 VARIABLE TABLES ================\n")

for fname in all_files:
    fp_orig = os.path.join(orig_dir, fname)
    fp_en = os.path.join(en_dir, fname)
    
    if not os.path.exists(fp_en):
        print(f"[FAIL] {fname}: Target file does not exist!")
        all_passed = False
        continue
        
    with open(fp_orig, 'rb') as f:
        orig_b = f.read()
    with open(fp_en, 'rb') as f:
        en_b = f.read()
        
    orig_lines = orig_b.decode('gbk', errors='replace').splitlines()
    try:
        en_lines = en_b.decode('gbk').splitlines()
    except Exception as e:
        print(f"[FAIL] {fname}: GBK decoding error: {e}")
        all_passed = False
        continue
        
    # 1. Line count
    line_match = (len(orig_lines) == len(en_lines))
    if not line_match:
        print(f"[FAIL] {fname}: Line count mismatch! ({len(orig_lines)} vs {len(en_lines)})")
        all_passed = False
    else:
        print(f"[PASS] {fname}: Line count matches ({len(orig_lines)} lines).")
        
    # 2. CRLF check
    has_crlf = (b'\r\n' in en_b)
    if not has_crlf:
        print(f"[FAIL] {fname}: CRLF line endings missing!")
        all_passed = False
    else:
        print(f"[PASS] {fname}: CRLF line endings verified.")
        
    # 3. Column count and Chinese comment check
    col_fail = 0
    cn_fail = 0
    var_mismatch = 0
    
    for idx, (ol, el) in enumerate(zip(orig_lines, en_lines)):
        op = ol.split(',')
        ep = el.split(',')
        if len(ep) != 10:
            col_fail += 1
        if idx > 0:
            if op[1] != ep[1]:
                var_mismatch += 1
            # Check comment
            c = ep[7]
            if re.search(r'[\u4e00-\u9fff]', c):
                cn_fail += 1
                
    if col_fail > 0:
        print(f"[FAIL] {fname}: {col_fail} lines do not have 10 parts (9 columns + trailing comma)!")
        all_passed = False
    else:
        print(f"[PASS] {fname}: 100% 9-column CSV format preserved.")
        
    if var_mismatch > 0:
        print(f"[FAIL] {fname}: {var_mismatch} variable names modified!")
        all_passed = False
    else:
        print(f"[PASS] {fname}: 100% variable names preserved (Option B compliant).")
        
    if cn_fail > 0:
        print(f"[FAIL] {fname}: {cn_fail} lines have Chinese characters in comments!")
        all_passed = False
    else:
        print(f"[PASS] {fname}: 0 Chinese characters in comments (100% Pure English).")
        
    print("-" * 65)

print(f"\nFINAL VERIFICATION RESULT: {'ALL PASS (100% SUCCESS)' if all_passed else 'FAILED'}")
