# -*- coding: utf-8 -*-
import os, sys, re
sys.stdout.reconfigure(encoding='utf-8')

src_file = r'c:\Users\fubai\Documents\BaiduSyncdisk\项目\CT173-美国康宁-6月-付白杨\PLC+HMI程序\康宁\1-封边机\io注释_备份_原始留档\变量表\安全继电器_变量表.csv'
dst_en_file = r'c:\Users\fubai\Documents\BaiduSyncdisk\项目\CT173-美国康宁-6月-付白杨\PLC+HMI程序\康宁\1-封边机\变量表\安全继电器_变量表.csv'

with open(src_file, 'rb') as f:
    orig_b = f.read()
with open(dst_en_file, 'rb') as f:
    en_b = f.read()

orig_lines = orig_b.decode('gbk').splitlines()
en_lines = en_b.decode('gbk').splitlines()

line_match = (len(orig_lines) == len(en_lines))
has_crlf = (b'\r\n' in en_b)

col_fail = 0
cn_fail = 0
var_mismatch = 0

for idx, (ol, el) in enumerate(zip(orig_lines, en_lines)):
    o_parts = ol.split(',')
    e_parts = el.split(',')
    if len(e_parts) != len(o_parts) or len(e_parts) != 10:
        col_fail += 1
    if idx > 0:
        if o_parts[1] != e_parts[1]:
            var_mismatch += 1
        c = e_parts[7]
        if re.search(r'[\u4e00-\u9fff]', c):
            cn_fail += 1
            print(f'Line {idx} comment has Chinese: {c}')

print(f'Line count check: {len(orig_lines)} == {len(en_lines)} -> {line_match}')
print(f'CRLF check: {has_crlf}')
print(f'Column count check: failures = {col_fail}')
print(f'Variable name integrity (Option B): mismatches = {var_mismatch}')
print(f'Comment zero Chinese check: failures = {cn_fail}')

if line_match and has_crlf and col_fail == 0 and cn_fail == 0 and var_mismatch == 0:
    print('>>> ALL CHECKS PASSED (100% SUCCESS) <<<')
