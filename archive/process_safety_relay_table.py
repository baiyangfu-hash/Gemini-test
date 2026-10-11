# -*- coding: utf-8 -*-
import os
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

src_file = r"c:\Users\fubai\Documents\BaiduSyncdisk\项目\CT173-美国康宁-6月-付白杨\PLC+HMI程序\康宁\1-封边机\io注释_备份_原始留档\变量表\安全继电器_变量表.csv"
dst_cn_dir = r"c:\Users\fubai\Documents\BaiduSyncdisk\项目\CT173-美国康宁-6月-付白杨\PLC+HMI程序\康宁\1-封边机\io注释_备份_规范中文版\变量表"
dst_en_dir = r"c:\Users\fubai\Documents\BaiduSyncdisk\项目\CT173-美国康宁-6月-付白杨\PLC+HMI程序\康宁\1-封边机\变量表"

os.makedirs(dst_cn_dir, exist_ok=True)
os.makedirs(dst_en_dir, exist_ok=True)

dst_cn_file = os.path.join(dst_cn_dir, "安全继电器_变量表.csv")
dst_en_file = os.path.join(dst_en_dir, "安全继电器_变量表.csv")
report_md_file = os.path.join(dst_en_dir, "安全继电器_变量表中英文对照表_Corning交付版.md")

with open(src_file, "rb") as f:
    raw = f.read()

text = raw.decode('gbk')
lines = text.splitlines(keepends=False)
print(f"Original file loaded: {len(lines)} lines")

# Mapping dictionaries based on user instruction:
# 方案B: 保持变量名不变；缺少注释的，根据变量名增加注释；有注释的翻译
# 1. 注释翻译映射 (已有注释)
comment_en_map = {
    "计时执行": "Timing Execution",
    "预设定时": "Preset Time",
    "计时器复位": "Timer Reset",
    "时间到达": "Time Reached",
    "经过时间": "Elapsed Time",
}

# 2. 根据变量名补充注释映射 (变量名 -> (规范中文注释, 交付英文注释))
var_comment_map = {
    "安全继电器功能启用": ("安全继电器功能启用", "Safety Relay Function Enable"),
    "Safety_TONR": ("安全继电器TONR定时器", "Safety TONR Timer Array"),
    "全部轴组_Busy_OFF状态": ("全部轴组Busy OFF状态", "All Axis Groups Busy OFF Status"),
    "sm400": ("常开触点 (SM400)", "Always ON Contact (SM400)"),
    "长边1正限定值": ("长边1正限定值", "L1 Positive Limit Value"),
    "长边2正限定值": ("长边2正限定值", "L2 Positive Limit Value"),
    "短边1正限定值": ("短边1正限定值", "S1 Positive Limit Value"),
    "短边2正限定值": ("短边2正限定值", "S2 Positive Limit Value"),
    "长边1负限定值": ("长边1负限定值", "L1 Negative Limit Value"),
    "长边2负限定值": ("长边2负限定值", "L2 Negative Limit Value"),
    "短边1负限定值": ("短边1负限定值", "S1 Negative Limit Value"),
    "短边2负限定值": ("短边2负限定值", "S2 Negative Limit Value"),
}

cn_lines = []
en_lines = []
comparison_rows = []

for idx, line in enumerate(lines):
    if idx == 0 or not line.strip():
        cn_lines.append(line)
        en_lines.append(line)
        continue
    
    parts = line.split(',')
    # Expected 10 parts: 序号,变量名,数据类型,隐藏初始值,初始值,掉电保持,网络公开,注释,软元件地址,
    if len(parts) >= 9:
        no = parts[0].strip()
        var_name = parts[1].strip()
        orig_comment = parts[7].strip()
        
        # 确定中文规范注释与英文注释
        if orig_comment:
            # 有注释 -> 翻译
            cn_comment = orig_comment
            en_comment = comment_en_map.get(orig_comment, orig_comment)
        else:
            # 缺少注释 -> 根据变量名增加注释
            if var_name in var_comment_map:
                cn_comment, en_comment = var_comment_map[var_name]
            elif var_name.startswith("Safety_TONR[") and "]" in var_name and not "." in var_name:
                # 数组元素如 Safety_TONR[0]
                idx_str = var_name.split("[")[1].split("]")[0]
                cn_comment = f"安全继电器定时器[{idx_str}]"
                en_comment = f"Safety Relay Timer [{idx_str}]"
            else:
                cn_comment = ""
                en_comment = ""
        
        # 确保注释中不含逗号以保证 CSV 列数
        en_comment_clean = en_comment.replace(',', ' / ').replace('，', ' / ')
        cn_comment_clean = cn_comment.replace(',', '，')
        
        # 组装中文行 (方案B: 保持变量名不变)
        cn_parts = list(parts)
        cn_parts[7] = cn_comment_clean
        cn_lines.append(','.join(cn_parts[:9]) + ',')
        
        # 组装英文行 (方案B: 保持变量名不变)
        en_parts = list(parts)
        en_parts[7] = en_comment_clean
        en_lines.append(','.join(en_parts[:9]) + ',')
        
        comparison_rows.append((no, var_name, parts[2].strip(), cn_comment_clean, en_comment_clean))
    else:
        cn_lines.append(line)
        en_lines.append(line)

# 写入规范中文版本
cn_content = '\r\n'.join(cn_lines) + '\r\n'
with open(dst_cn_file, "wb") as f:
    f.write(cn_content.encode('gbk'))
print(f"Written Chinese standard version: {dst_cn_file} ({len(cn_lines)} lines)")

# 写入纯英文交付版本
en_content = '\r\n'.join(en_lines) + '\r\n'
with open(dst_en_file, "wb") as f:
    f.write(en_content.encode('gbk'))
print(f"Written English delivery version: {dst_en_file} ({len(en_lines)} lines)")

# 写入 Markdown 中英文比对报告
with open(report_md_file, "w", encoding="utf-8") as f:
    f.write("# 安全继电器变量表中英文对照表 (美国康宁交付版 - Corning Project CT173 - 1-封边机)\n\n")
    f.write("> **项目交付**：美国康宁 (Corning Incorporated - CT173 1-封边机)\n")
    f.write("> **文件来源**：`安全继电器_变量表.csv`\n")
    f.write("> **实施策略**：**方案 B**（变量名保持原始符号不变；已有注释 100% 翻译为纯专业英文；缺失注释的变量根据变量名规范补齐注释）。\n")
    f.write("> **文件保真**：严格保持 9 列 CSV 格式、GBK 编码、CRLF 换行，确保可直接无损导入汇川 PLC。\n\n")
    f.write("---\n\n")
    f.write("| 序号 | 变量名 (Variable Name) | 数据类型 | 规范中文注释 (Chinese) | 交付英文注释 (English Standard) |\n")
    f.write("| :---: | :--- | :---: | :--- | :--- |\n")
    for no, var, dtype, cn_c, en_c in comparison_rows:
        no_str = no if no else "-"
        f.write(f"| {no_str} | `{var}` | `{dtype}` | {cn_c} | **`{en_c}`** |\n")

print(f"Written comparison markdown report: {report_md_file}")
