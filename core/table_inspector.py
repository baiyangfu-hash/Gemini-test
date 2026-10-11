# -*- coding: utf-8 -*-
"""
=============================================================================
PLC Table Toolkit - 变量与工业文档只读对比检视服务 (TableInspector)
=============================================================================
设计定位：
  独立领域服务层 (Domain Service)，遵循单一职责原则 (SRP) 与高内聚低耦合。
  负责只读解析原始留档与交付成果，执行逐行对齐、数据类型感知、类型分布统计
  与中英翻译状态判定。

安全保证：
  100% 纯只读 (Zero Mutation)：底层采用非排他只读文件流，不产生任何写操作，
  不改变任何字节、CRLF 换行或编码，绝不影响自动化质量验收 (TableVerifier)。
=============================================================================
"""

import os
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Tuple


@dataclass
class VariableInspectionRecord:
    """单个变量检视对比记录实体"""
    no: str = ""                         # 序号 (Col 0)
    name: str = ""                       # 变量名 (Col 1)
    data_type: str = ""                  # 数据类型 (Col 2，如 BOOL, DINT, REAL, ARRAY, ST_*)
    init_val: str = ""                   # 初始值 (Col 4)
    orig_comment: str = ""               # 原始中文注释/文档 (Col 7)
    delivered_comment: str = ""          # 变更后纯英文交付注释/文档
    status: str = "unchanged"            # 'translated' | 'derived' | 'unchanged' | 'alert'
    is_diff: bool = False                # 是否存在变更 (注释翻译或推导)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TableInspectionResult:
    """单个变量表全量检视分析结果"""
    file_name: str = ""                  # 表格文件名 (如 产量_变量表.csv)
    src_path: str = ""                   # 原始留档文件绝对路径
    target_path: str = ""                # 交付文件绝对路径
    total_rows: int = 0                  # 总变量数
    type_breakdown: Dict[str, int] = field(default_factory=dict)     # 数据类型分布统计 {BOOL: 120, ...}
    status_counts: Dict[str, int] = field(default_factory=dict)      # 变更状态统计 {translated: 80, ...}
    has_chinese_residue: bool = False    # 交付文档是否存在未翻译中文残留
    residue_count: int = 0               # 违规中文残留条数
    records: List[VariableInspectionRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["records"] = [r.to_dict() if hasattr(r, "to_dict") else r for r in self.records]
        return d


class TableInspector:
    """高内聚低耦合的 PLC 表格只读检视器与对比引擎"""

    RE_CHINESE = re.compile(r'[\u4e00-\u9fff]')

    @classmethod
    def _read_csv_lines(cls, file_path: str) -> List[str]:
        """以纯只读模式安全读取 CSV/TSV 文件所有行 (自动兼容 UTF-16 / GBK / UTF-8)"""
        if not file_path or not os.path.exists(file_path):
            return []

        # 优先探测 UTF-16 BOM
        try:
            with open(file_path, "rb") as bf:
                b_head = bf.read(4)
            if b_head.startswith(b'\xff\xfe') or b_head.startswith(b'\xfe\xff'):
                with open(file_path, "r", encoding="utf-16", errors="replace") as f:
                    return f.readlines()
        except Exception:
            pass

        # 纯只读打开，绝不产生写入锁
        for enc in ["utf-16", "gbk", "utf-8", "cp936", "latin1"]:
            try:
                with open(file_path, "r", encoding=enc, errors="replace") as f:
                    return f.readlines()
            except Exception:
                continue
        return []

    @classmethod
    def _parse_row_tokens(cls, line: str) -> Tuple[str, str, str, str, str]:
        """
        智能解析行结构 (自动兼容汇川 9 列 CSV 与三菱 GX Works3 27 列 TSV / 2 列 IO 表)
        返回 (no, name, data_type, init_val, comment)
        """
        line = line.strip('\r\n')
        if not line:
            return ("", "", "", "", "")

        # 1. 优先按制表符 \t 切割 (三菱 GX Works3)
        if '\t' in line:
            parts = [p.strip().strip('"') for p in line.split('\t')]
            if len(parts) >= 15:
                # 三菱 27 列 GVL 标签表:
                # Col 0: 类 (VAR_INPUT)
                # Col 1: 标签名
                # Col 2: 数据类型
                # Col 4: 初始值
                # Col 7: 注释
                # Col 13: English
                # Col 14: Chinese Simplified
                # Col 18: Italian/Italiano
                no = parts[0]
                name = parts[1] if len(parts) > 1 else ""
                dtype = parts[2] if len(parts) > 2 else ""
                init_val = parts[4] if len(parts) > 4 else ""
                comm = parts[13] or parts[18] or parts[14] or parts[7]
                if not comm and any('\u4e00' <= c <= '\u9fff' for c in name):
                    comm = name
                return (no, name, dtype, init_val, comm)
            elif len(parts) >= 2:
                # 三菱 2 列 IO 软元件表
                dev = parts[0]
                comm = parts[1]
                return ("-", dev, "DEVICE", "", comm)
            else:
                return ("", parts[0], "", "", "")

        # 2. 汇川标准 9 列逗号分隔 (Inovance CSV)
        parts = line.split(',')
        no = parts[0].strip() if len(parts) > 0 else ""
        name = parts[1].strip() if len(parts) > 1 else ""
        data_type = parts[2].strip() if len(parts) > 2 else ""
        init_val = parts[4].strip() if len(parts) > 4 else ""
        comment = parts[7].strip() if len(parts) > 7 else ""

        return (no, name, data_type, init_val, comment)

    @classmethod
    def inspect_single_table(cls, src_path: str, target_path: Optional[str] = None) -> TableInspectionResult:
        """
        对单个变量表执行只读检视与中英文档对齐分析
        :param src_path: 原始留档 CSV/TSV 路径
        :param target_path: 纯英文/意文交付 CSV/TSV 路径 (可选)
        """
        result = TableInspectionResult()
        result.file_name = os.path.basename(src_path if src_path else target_path)
        result.src_path = os.path.abspath(src_path) if src_path else ""
        result.target_path = os.path.abspath(target_path) if target_path else ""

        src_lines = cls._read_csv_lines(src_path) if src_path else []
        target_lines = cls._read_csv_lines(target_path) if target_path else []

        # 智能去除首行 POU 名称与表头
        def strip_headers(lines: List[str]) -> List[str]:
            if not lines:
                return []
            idx = 0
            # 若第 1 行是单一引号包含的 POU 名称且不含制表符/逗号
            if lines[0].strip().startswith('"') and '\t' not in lines[0] and ',' not in lines[0]:
                idx = 1
            # 滤除表头行
            if idx < len(lines):
                first_row = lines[idx]
                if any(k in first_row for k in ["标签名", "软元件名", "序号", "变量名"]):
                    idx += 1
            return [l for l in lines[idx:] if l.strip()]

        src_data = strip_headers(src_lines)
        target_data = strip_headers(target_lines)

        max_rows = max(len(src_data), len(target_data))
        result.total_rows = max_rows

        type_map: Dict[str, int] = {}
        status_map: Dict[str, int] = {"translated": 0, "derived": 0, "unchanged": 0, "alert": 0}
        residue_count = 0

        for i in range(max_rows):
            s_line = src_data[i] if i < len(src_data) else ""
            t_line = target_data[i] if i < len(target_data) else ""

            s_no, s_name, s_type, s_init, s_comm = cls._parse_row_tokens(s_line)
            t_no, t_name, t_type, t_init, t_comm = cls._parse_row_tokens(t_line)

            # 字段优先级：以交付表为主，交付表缺漏则以原始表兜底
            no = t_no or s_no or str(i + 1)
            name = t_name or s_name
            dtype = t_type or s_type or "UNKNOWN"
            init_val = t_init or s_init
            orig_comment = s_comm
            deliv_comment = t_comm if t_line else s_comm

            # 统计数据类型分布
            norm_type = dtype.split()[0].upper() if dtype else "EMPTY"
            if norm_type.startswith("ARRAY"):
                norm_type = "ARRAY"
            elif norm_type.startswith("ST_") or norm_type.startswith("DUT_"):
                norm_type = "STRUCT/DUT"
            type_map[norm_type] = type_map.get(norm_type, 0) + 1

            # 判定变更状态
            has_cn_in_deliv = bool(cls.RE_CHINESE.search(deliv_comment))
            has_cn_in_orig = bool(cls.RE_CHINESE.search(orig_comment))

            if has_cn_in_deliv and target_path:
                status = "alert"
                residue_count += 1
            elif not orig_comment and (cls.RE_CHINESE.search(name) or deliv_comment):
                status = "derived"
            elif has_cn_in_orig and deliv_comment != orig_comment:
                status = "translated"
            else:
                status = "unchanged"

            status_map[status] = status_map.get(status, 0) + 1
            is_diff = (deliv_comment != orig_comment) or (status in ["translated", "derived"])

            rec = VariableInspectionRecord(
                no=no,
                name=name,
                data_type=dtype,
                init_val=init_val,
                orig_comment=orig_comment,
                delivered_comment=deliv_comment,
                status=status,
                is_diff=is_diff
            )
            result.records.append(rec)

        result.type_breakdown = dict(sorted(type_map.items(), key=lambda x: x[1], reverse=True))
        result.status_counts = status_map
        result.residue_count = residue_count
        result.has_chinese_residue = (residue_count > 0)

        return result

    @classmethod
    def list_machine_available_tables(cls, machine_dir: str) -> List[Dict[str, Any]]:
        """
        自动扫描指定机台目录下的所有可用全局变量表与 IO 表 (支持汇川与三菱项目目录)
        返回列表: [{"file_name": "...", "src_path": ..., "target_path": ..., "row_count": ...}]
        """
        if not machine_dir or not os.path.exists(machine_dir):
            return []

        search_dirs = [
            os.path.join(machine_dir, "io注释_备份_原始留档", "变量表"),
            os.path.join(machine_dir, "变量表"),
            os.path.join(machine_dir, "2.PLC", "变量表"),
            os.path.join(machine_dir, "2.PLC", "IO注释"),
            os.path.join(machine_dir, "2.PLC"),
            os.path.join(machine_dir, "IO注释"),
            machine_dir
        ]

        discovered: Dict[str, Dict[str, Any]] = {}

        for sdir in search_dirs:
            if not os.path.exists(sdir) or not os.path.isdir(sdir):
                continue
            try:
                for f in sorted(os.listdir(sdir)):
                    if f.endswith((".csv", ".tsv")) and not f.endswith("_new.csv"):
                        fp = os.path.join(sdir, f)
                        if f not in discovered:
                            orig_p = os.path.join(machine_dir, "io注释_备份_原始留档", "变量表", f)
                            deliv_p = os.path.join(machine_dir, "变量表", f)
                            if os.path.exists(orig_p) and os.path.exists(deliv_p):
                                src_p = orig_p
                                tgt_p = deliv_p
                            elif os.path.exists(orig_p):
                                src_p = orig_p
                                tgt_p = deliv_p if os.path.exists(deliv_p) else orig_p
                            else:
                                src_p = fp
                                tgt_p = fp

                            discovered[f] = {
                                "file_name": f,
                                "src_path": src_p,
                                "target_path": tgt_p,
                                "has_delivery": os.path.exists(tgt_p) and (tgt_p != src_p)
                            }
            except Exception:
                continue

        # 计算大致行数 (只读计数)
        table_list = list(discovered.values())
        for item in table_list:
            check_path = item["target_path"] or item["src_path"]
            lines = cls._read_csv_lines(check_path)
            # 去除表头行计数
            item["row_count"] = max(0, len(lines) - (2 if lines and '\t' in lines[0] else 1))

        return sorted(table_list, key=lambda x: x["file_name"])

    @classmethod
    def inspect_machine_overview(cls, machine_dir: str) -> Dict[str, Any]:
        """获取整个机台的变量全局体检与类型分布概览"""
        tables = cls.list_machine_available_tables(machine_dir)
        total_tables = len(tables)
        total_vars = sum(t.get("row_count", 0) for t in tables)

        overall_types: Dict[str, int] = {}
        for t in tables:
            sp = t.get("src_path", "")
            tp = t.get("target_path", "")
            res = cls.inspect_single_table(sp, tp)
            for k, v in res.type_breakdown.items():
                overall_types[k] = overall_types.get(k, 0) + v

        return {
            "machine_name": os.path.basename(machine_dir),
            "machine_dir": machine_dir,
            "total_tables": total_tables,
            "total_variables": total_vars,
            "overall_types": dict(sorted(overall_types.items(), key=lambda x: x[1], reverse=True)),
            "tables": tables
        }

    @classmethod
    def discover_machines(cls, workspace_dir: str) -> List[Dict[str, str]]:
        """
        全自动动态发现项目空间下的所有机台目录。
        支持：
          1. 优先扫描 workspace_dir/康宁 下的所有子目录
          2. 扫描 workspace_dir 本身的所有子目录 (包括三菱意大利产线等)
          3. 扫描规则: 包含 '变量表'、'2.PLC'、'IO注释' 文件夹或以 '_变量表.csv'、'.gx3' 结尾的文件
        返回: [{"name": "1-封边机", "path": "D:/.../1-封边机"}, ...]
        """
        results = []
        seen_paths = set()

        search_roots = []
        if workspace_dir:
            corning_p = os.path.join(workspace_dir, "康宁")
            if os.path.exists(corning_p):
                search_roots.append(corning_p)
            if os.path.exists(workspace_dir):
                search_roots.append(workspace_dir)

        for s_root in search_roots:
            try:
                for entry in sorted(os.listdir(s_root)):
                    sub_path = os.path.join(s_root, entry)
                    if not os.path.isdir(sub_path):
                        continue
                    if entry in ["自动翻译与规范化工具_Workflow", ".git", "__pycache__", "build", "dist"]:
                        continue

                    has_var = (
                        os.path.exists(os.path.join(sub_path, "变量表")) or
                        os.path.exists(os.path.join(sub_path, "2.PLC")) or
                        os.path.exists(os.path.join(sub_path, "IO注释")) or
                        os.path.exists(os.path.join(sub_path, "io注释_备份_原始留档", "变量表")) or
                        any(f.endswith(("_变量表.csv", ".gx3")) for f in os.listdir(sub_path) if os.path.isfile(os.path.join(sub_path, f)))
                    )
                    if has_var:
                        norm_p = os.path.normpath(sub_path)
                        if norm_p not in seen_paths:
                            seen_paths.add(norm_p)
                            results.append({"name": entry, "path": norm_p})
            except Exception:
                continue

        return results

