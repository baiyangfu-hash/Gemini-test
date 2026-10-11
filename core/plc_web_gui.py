# -*- coding: utf-8 -*-
"""
=============================================================================
PLC Table Toolkit - 现代轻量级本地 Web 控制台 (Local Web Console)
=============================================================================
特性：
  1. 零外部依赖：纯 Python 标准库 (http.server / urllib / json / webbrowser) 开发，免 pip。
  2. 浏览器即开：启动后自动在默认浏览器 (Edge / Chrome) 中弹出控制台界面。
  3. 跨平台免疫：不受 Windows 桌面会话、DPI 缩放或 Tkinter 窗口焦点限制。
  4. 全功能涵盖：整机交付、变量表批量处理、IO转换、5 重质量验收、术语即时沙盒。
  5. 变量与文档只读对比检视：
     - 数据类型 (DataType) 深度感知与分类徽章高亮 (BOOL / REAL / DINT / DUT / ARRAY)
     - 原始文档 vs 变更交付文档逐行 Side-by-Side 对齐
     - 毫秒级即时模糊搜索过滤，纯只读零副作用保障
=============================================================================
"""

import os
import sys
import json
import urllib.parse
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_ROOT = os.path.dirname(CURRENT_DIR)
for p in [CURRENT_DIR, WORKFLOW_ROOT, os.path.join(WORKFLOW_ROOT, "plugins")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from table_inspector import TableInspector
import plc_table_toolkit as toolkit

def find_machine_root(machine_name: str) -> str:
    if not machine_name:
        return ""
    if os.path.isabs(machine_name) and os.path.exists(machine_name):
        return machine_name
    ws_root = os.path.abspath(os.path.join(WORKFLOW_ROOT, ".."))
    try:
        discovered = TableInspector.discover_machines(ws_root)
        for m in discovered:
            if m["name"] == machine_name:
                return m["path"]
    except Exception:
        pass
    candidates = [
        os.path.join(WORKFLOW_ROOT, "..", "康宁", machine_name),
        os.path.join(WORKFLOW_ROOT, "康宁", machine_name),
        os.path.join(r"c:\Users\fubai\Documents\BaiduSyncdisk\项目\CT173-美国康宁-6月-付白杨\PLC+HMI程序", "康宁", machine_name),
        os.path.join(WORKFLOW_ROOT, "..", machine_name),
        os.path.join(WORKFLOW_ROOT, machine_name),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]

def find_plugin(plugin_filename: str) -> str:
    candidates = [
        os.path.join(WORKFLOW_ROOT, "plugins", plugin_filename),
        os.path.join(WORKFLOW_ROOT, plugin_filename),
        os.path.join(CURRENT_DIR, plugin_filename),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]

# 全局内存日志缓冲区
LOG_BUFFER: List[Dict[str, str]] = []
LOG_LOCK = threading.Lock()

def add_log(msg: str, tag: str = "INFO") -> None:
    with LOG_LOCK:
        LOG_BUFFER.append({"msg": msg, "tag": tag})
        if len(LOG_BUFFER) > 500:
            LOG_BUFFER.pop(0)

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Corning PLC Table Toolkit - 工业表格控制台</title>
    <style>
        :root {
            --primary: #005691;
            --primary-dark: #003D66;
            --bg: #F4F6F9;
            --card-bg: #FFFFFF;
            --text: #263238;
            --success: #2E7D32;
            --danger: #C62828;
            --warning: #EF6C00;
            --border: #CFD8DC;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
        body { background: var(--bg); color: var(--text); padding-bottom: 40px; }
        header { background: var(--primary); color: #fff; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        header h1 { font-size: 1.25rem; font-weight: 600; }
        header .badge { background: var(--primary-dark); font-size: 0.8rem; padding: 4px 10px; border-radius: 4px; }
        .container { max-width: 1180px; margin: 20px auto; padding: 0 16px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .full-width { grid-column: 1 / -1; }
        .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .card h2 { font-size: 1.05rem; margin-bottom: 12px; color: var(--primary); border-bottom: 2px solid #ECEFF1; padding-bottom: 6px; }
        .btn { display: inline-flex; align-items: center; justify-content: center; padding: 10px 18px; border: none; border-radius: 6px; font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: 0.2s; text-decoration: none; }
        .btn-primary { background: var(--primary); color: #fff; }
        .btn-primary:hover { background: var(--primary-dark); }
        .btn-success { background: var(--success); color: #fff; }
        .btn-success:hover { background: #1B5E20; }
        .btn-outline { background: transparent; border: 1px solid var(--primary); color: var(--primary); }
        .btn-outline:hover { background: #E3F2FD; }
        .input-group { margin-bottom: 12px; }
        .input-group label { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 4px; color: #455A64; }
        .input-group input, .input-group select { width: 100%; padding: 8px 12px; border: 1px solid var(--border); border-radius: 4px; font-size: 0.9rem; }
        .btn-group { display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }
        #console { background: #1E1E1E; color: #D4D4D4; font-family: "Consolas", monospace; font-size: 0.85rem; height: 220px; overflow-y: auto; padding: 12px; border-radius: 6px; line-height: 1.5; white-space: pre-wrap; }
        .log-PASS { color: #81C784; font-weight: bold; }
        .log-FAIL { color: #E57373; font-weight: bold; }
        .log-WARN { color: #FFD54F; }
        .log-INFO { color: #81D4FA; }
        .term-box { display: flex; gap: 8px; margin-bottom: 10px; }
        .term-box input { flex: 1; padding: 8px 12px; border: 1px solid var(--border); border-radius: 4px; }
        .term-res { background: #ECEFF1; padding: 10px; border-radius: 4px; margin-top: 8px; font-family: monospace; font-size: 0.95rem; }
        .quick-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
        .chip { background: #E0E0E0; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; cursor: pointer; }
        .chip:hover { background: #CFD8DC; }
        
        /* 变量检视器专属样式 */
        .inspect-controls { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 14px; }
        .inspect-controls select, .inspect-controls input { padding: 8px 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 0.9rem; }
        .inspect-stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; align-items: center; }
        .stat-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; background: #ECEFF1; color: #37474F; }
        .stat-pill.pill-green { background: #E8F5E9; color: #2E7D32; }
        .stat-pill.pill-blue { background: #E3F2FD; color: #1565C0; }
        .stat-pill.pill-amber { background: #FFF8E1; color: #F57F17; }
        .stat-pill.pill-red { background: #FFEBEE; color: #C62828; }
        
        .grid-container { max-height: 480px; overflow-y: auto; border: 1px solid var(--border); border-radius: 6px; }
        .inspect-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; text-align: left; }
        .inspect-table th { position: sticky; top: 0; background: #ECEFF1; color: #37474F; padding: 10px 12px; font-weight: 600; border-bottom: 2px solid var(--border); z-index: 2; }
        .inspect-table td { padding: 8px 12px; border-bottom: 1px solid #EEEEEE; vertical-align: middle; }
        .inspect-table tr:hover { background-color: #F5F9FD; }
        .var-name { font-family: "Consolas", monospace; font-weight: 600; color: #0D47A1; }
        
        /* 数据类型高亮徽章 */
        .badge-type { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; font-family: "Consolas", monospace; }
        .type-BOOL { background: #E8F5E9; color: #1B5E20; border: 1px solid #A5D6A7; }
        .type-REAL, .type-LREAL { background: #E0F7FA; color: #006064; border: 1px solid #80DEEA; }
        .type-INT, .type-DINT, .type-WORD, .type-DWORD { background: #E3F2FD; color: #0D47A1; border: 1px solid #90CAF9; }
        .type-TIME { background: #FFF3E0; color: #E65100; border: 1px solid #FFCC80; }
        .type-STRING { background: #FFFDE7; color: #F57F17; border: 1px solid #FFF59D; }
        .type-ARRAY { background: #EDE7F6; color: #4A148C; border: 1px solid #D1C4E9; }
        .type-STRUCT, .type-DUT { background: #F3E5F5; color: #6A1B9A; border: 1px solid #CE93D8; }
        .type-OTHER { background: #ECEFF1; color: #37474F; border: 1px solid #B0BEC5; }

        /* 变更状态标签 */
        .status-badge { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 0.75rem; font-weight: 600; }
        .status-translated { background: #E8F5E9; color: #2E7D32; }
        .status-derived { background: #FFF8E1; color: #EF6C00; }
        .status-unchanged { background: #F5F5F5; color: #757575; }
        .status-alert { background: #FFEBEE; color: #C62828; font-weight: bold; }
    </style>
</head>
<body>
    <header>
        <h1>⚡ Corning PLC 表格规范化与微内核套件 (Web 控制台)</h1>
        <span class="badge">Local Web Console v2.1</span>
    </header>

    <div class="container">
        <!-- 卡片 1: 变量与工业文档只读对比检视器 (全宽置顶) -->
        <div class="card full-width">
            <h2>📊 变量与工业文档只读对比检视器 (Variable & Document Inspector)</h2>
            <p style="font-size:0.85rem; color:#546E7A; margin-bottom:12px;">
                🔒 <strong>100% 纯只读安全模式</strong>：非排他流读取，不产生任何写入与锁冲突。直观检视原始中文文档、纯英文交付文档、IEC 61131-3 数据类型与变更状态。
            </p>

            <div class="inspect-controls" style="margin-bottom:8px;">
                <label style="font-weight:600; font-size:0.9rem;">PLC 品牌/平台:</label>
                <select id="inspectPlatform" onchange="onPlatformChanged()" style="min-width:240px;">
                    <option value="auto" selected>⚡ 自动智能识别 (Auto Detect)</option>
                    <option value="autoshop">汇川 AutoShop (H3U/H5U 小型PLC)</option>
                    <option value="inoproshop">汇川 InoProShop (CODESYS/AM/AC 中大型PLC)</option>
                    <option value="mitsubishi">三菱 GX Works3 (iQ-R/iQ-F 平台)</option>
                </select>

                <label style="font-weight:600; font-size:0.9rem; margin-left:8px;">目标交付语言:</label>
                <select id="inspectLang" onchange="onLangChanged()" style="min-width:160px;">
                    <option value="en" selected>English (纯英文交付)</option>
                    <option value="it">Italiano (意大利语交付)</option>
                </select>
            </div>

            <div class="inspect-controls">
                <label style="font-weight:600; font-size:0.9rem;">选择机台:</label>
                <select id="inspectMachine" onchange="onMachineChanged()">
                    <option value="3-修边机" selected>3-修边机 (当前基准)</option>
                    <option value="1-封边机">1-封边机</option>
                    <option value="2-撕胶带机">2-撕胶带机</option>
                </select>
                <button class="btn btn-outline" style="padding:6px 10px; font-size:0.85rem;" onclick="promptCustomMachine()">📁 外部机台...</button>

                <label style="font-weight:600; font-size:0.9rem;">选择变量表:</label>
                <select id="inspectTableSelect" onchange="onTableChanged()" style="min-width:220px;">
                    <option value="">正在加载变量表清单...</option>
                </select>

                <input type="text" id="inspectSearch" placeholder="🔍 输入变量名、数据类型或中英注释实时过滤..." style="flex:1; min-width:260px;" oninput="filterRows()">

                <button class="btn btn-outline" style="padding:6px 12px; font-size:0.85rem;" onclick="refreshCurrentTable()">🔄 刷新数据</button>
            </div>

            <!-- 统计标签栏 -->
            <div class="inspect-stats" id="statsBar">
                <span class="stat-pill pill-blue" id="statTotalVars">总变量数: -</span>
                <span class="stat-pill pill-green" id="statPureEnglish">质量门禁: 检查中</span>
                <span id="typeBadges"></span>
            </div>

            <!-- 表格滚动视图 -->
            <div class="grid-container">
                <table class="inspect-table">
                    <thead>
                        <tr>
                            <th style="width: 60px; text-align:center;">序号</th>
                            <th style="width: 220px;">变量名 (Variable Name)</th>
                            <th style="width: 140px;">数据类型 (DataType)</th>
                            <th>原始文档 / 中文注释 (Original)</th>
                            <th>变更后文档 / 纯英文交付 (Delivered)</th>
                            <th style="width: 90px; text-align:center;">状态</th>
                        </tr>
                    </thead>
                    <tbody id="inspectBody">
                        <tr><td colspan="6" style="text-align:center; padding:30px; color:#78909C;">正在加载表格数据...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 卡片 2: 整机一键交钥匙交付 -->
        <div class="card full-width">
            <h2>🏭 整机一键交钥匙交付 (Turnkey Pipeline)</h2>
            <p style="font-size:0.9rem; color:#546E7A; margin-bottom:12px;">
                自动串联：扫描基准表 &rarr; 策略 B 批量翻译 (100% 保持变量名不变) &rarr; 规范中文备份 &rarr; 导出单一 Markdown 总表 &rarr; 5 重自动化严苛质量门禁。
            </p>
            <div style="display:flex; gap:12px; align-items:center;">
                <button class="btn btn-success" style="font-size:1.05rem;" onclick="runTurnkey('3-修边机')">🚀 一键执行：3-修边机全量交付与质检 (12个基准表)</button>
                <button class="btn btn-outline" onclick="runTurnkey('1-封边机')">1-封边机</button>
                <button class="btn btn-outline" onclick="runTurnkey('2-撕胶带机')">2-撕胶带机</button>
            </div>
        </div>

        <!-- 卡片 3: 质量验收门禁 -->
        <div class="card">
            <h2>✅ 自动化质量验收门禁 (Verification Gate)</h2>
            <p style="font-size:0.85rem; color:#546E7A; margin-bottom:12px;">对交付目录执行行数吻合、CRLF换行、9列格式保真、0中文残留 5 重基线断言。</p>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="runVerify('3-修边机')">🛡️ 质检 3-修边机交付目录</button>
            </div>
        </div>

        <!-- 卡片 4: 工业术语沙盒即时测验 -->
        <div class="card">
            <h2>🔍 工业术语沙盒即时测验</h2>
            <div class="term-box">
                <input type="text" id="termInput" placeholder="输入中文电气注释或变量名..." value="伺服原点门型光电检测异常，曲线类型：0，T型；1，S型">
                <button class="btn btn-primary" onclick="testTerm()">立即翻译</button>
            </div>
            <div class="term-res" id="termOutput">纯英文译文将展示在此处</div>
            <div class="quick-chips">
                <span class="chip" onclick="setTerm('修边刀上升到位')">修边刀上升到位</span>
                <span class="chip" onclick="setTerm('旋转角度：90°')">旋转角度：90°</span>
                <span class="chip" onclick="setTerm('温度设定：25℃')">温度设定：25℃</span>
                <span class="chip" onclick="setTerm('PLCOpen状态机，故障停机')">PLCOpen状态机</span>
            </div>
        </div>

        <!-- 卡片 5: 实时日志控制台 -->
        <div class="card full-width">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <h2 style="margin:0; border:none;">🖥️ 实时执行监控控制台 (Execution Log)</h2>
                <button class="btn btn-outline" style="padding:4px 10px; font-size:0.8rem;" onclick="clearLogs()">清空控制台</button>
            </div>
            <div id="console">正在连接服务日志...</div>
        </div>
    </div>

    <script>
        let currentTableData = null;

        function getTypeBadgeClass(dtype) {
            if (!dtype) return "type-OTHER";
            const up = dtype.toUpperCase();
            if (up === "BOOL") return "type-BOOL";
            if (up === "REAL" || up === "LREAL") return "type-REAL";
            if (["INT", "DINT", "SINT", "UINT", "UDINT", "WORD", "DWORD"].includes(up)) return "type-INT";
            if (up === "TIME") return "type-TIME";
            if (up === "STRING") return "type-STRING";
            if (up.startsWith("ARRAY")) return "type-ARRAY";
            if (up.startsWith("ST_") || up.startsWith("DUT_")) return "type-STRUCT";
            return "type-OTHER";
        }

        function getStatusBadge(st) {
            if (st === "translated") return '<span class="status-badge status-translated">🟢 已翻译</span>';
            if (st === "derived") return '<span class="status-badge status-derived">🟡 智能推导</span>';
            if (st === "alert") return '<span class="status-badge status-alert">⚠️ 中文残留</span>';
            return '<span class="status-badge status-unchanged">⚪ 未变更</span>';
        }

        async function loadMachineList() {
            try {
                const res = await fetch("/api/inspect/machines");
                const data = await res.json();
                if (data.machines && data.machines.length > 0) {
                    const sel = document.getElementById("inspectMachine");
                    sel.innerHTML = "";
                    data.machines.forEach(m => {
                        const opt = document.createElement("option");
                        opt.value = m.name;
                        opt.textContent = m.name;
                        if (m.name.includes("3-修边机")) opt.selected = true;
                        sel.appendChild(opt);
                    });
                }
            } catch(e) {
                console.error("动态机台加载失败", e);
            }
            onMachineChanged();
        }

        function promptCustomMachine() {
            const p = prompt("请输入机台文件夹绝对路径 (例如 D:\\Project\\4-贴标机):");
            if (p && p.trim()) {
                const trimmed = p.trim();
                const sel = document.getElementById("inspectMachine");
                const opt = document.createElement("option");
                opt.value = trimmed;
                opt.textContent = "[外部] " + trimmed.split(/[\\/]/).pop();
                opt.selected = true;
                sel.appendChild(opt);
                onMachineChanged();
            }
        }

        async function onMachineChanged() {
            const m = document.getElementById("inspectMachine").value;
            const res = await fetch("/api/inspect/tables?machine=" + encodeURIComponent(m));
            const data = await res.json();
            const sel = document.getElementById("inspectTableSelect");
            sel.innerHTML = "";
            if (data.tables && data.tables.length > 0) {
                data.tables.forEach(t => {
                    const opt = document.createElement("option");
                    opt.value = t.file_name;
                    opt.textContent = t.file_name + " (" + (t.row_count || 0) + " 行)";
                    sel.appendChild(opt);
                });
                onTableChanged();
            } else {
                sel.innerHTML = '<option value="">未找到变量表文件</option>';
                document.getElementById("inspectBody").innerHTML = '<tr><td colspan="6" style="text-align:center; padding:30px;">无可用变量表</td></tr>';
            }
        }

        function onPlatformChanged() {
            onTableChanged();
        }

        function onLangChanged() {
            onTableChanged();
            testTerm();
        }

        async function onTableChanged() {
            const m = document.getElementById("inspectMachine").value;
            const f = document.getElementById("inspectTableSelect").value;
            const plat = document.getElementById("inspectPlatform").value;
            const lang = document.getElementById("inspectLang").value;
            if (!f) return;

            document.getElementById("inspectBody").innerHTML = '<tr><td colspan="6" style="text-align:center; padding:30px; color:#546E7A;">正在加载 ' + f + ' 变量及中英对照数据...</td></tr>';
            
            const res = await fetch("/api/inspect/detail?machine=" + encodeURIComponent(m) + "&file=" + encodeURIComponent(f) + "&platform=" + encodeURIComponent(plat) + "&lang=" + encodeURIComponent(lang));
            const data = await res.json();
            currentTableData = data;
            renderInspector(data);
        }

        function refreshCurrentTable() {
            onTableChanged();
        }

        function renderInspector(data) {
            let plat = "自动识别";
            if (data.platform === "mitsubishi") plat = "三菱 GX Works3";
            else if (data.platform === "inoproshop") plat = "汇川 InoProShop (CODESYS)";
            else if (data.platform === "autoshop" || data.platform === "inovance") plat = "汇川 AutoShop (小型PLC)";

            const lang = document.getElementById("inspectLang").value === "it" ? "Italiano" : "English";
            document.getElementById("statTotalVars").textContent = "平台: " + plat + " | 语种: " + lang + " | 总变量/点位数: " + (data.total_rows || 0);
            
            const pe = document.getElementById("statPureEnglish");
            if (data.has_chinese_residue) {
                pe.className = "stat-pill pill-red";
                pe.textContent = "⚠️ 存在未翻译中文: " + data.residue_count + " 处";
            } else {
                pe.className = "stat-pill pill-green";
                pe.textContent = "✅ 交付注释 0 中文残留 (100% " + (lang === "Italiano" ? "Pure Italian" : "Pure English") + ")";
            }

            // 渲染数据类型标签
            const tb = document.getElementById("typeBadges");
            tb.innerHTML = "";
            if (data.type_breakdown) {
                Object.entries(data.type_breakdown).slice(0, 5).forEach(([tname, count]) => {
                    const span = document.createElement("span");
                    span.className = "stat-pill";
                    span.textContent = tname + ": " + count;
                    tb.appendChild(span);
                });
            }

            filterRows();
        }

        function filterRows() {
            if (!currentTableData || !currentTableData.records) return;
            const q = document.getElementById("inspectSearch").value.trim().toLowerCase();
            const tbody = document.getElementById("inspectBody");
            tbody.innerHTML = "";

            const filtered = currentTableData.records.filter(r => {
                if (!q) return true;
                return (r.name && r.name.toLowerCase().includes(q)) ||
                       (r.data_type && r.data_type.toLowerCase().includes(q)) ||
                       (r.orig_comment && r.orig_comment.toLowerCase().includes(q)) ||
                       (r.delivered_comment && r.delivered_comment.toLowerCase().includes(q));
            });

            if (filtered.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:30px; color:#9E9E9E;">无匹配的变量记录</td></tr>';
                return;
            }

            const limit = Math.min(filtered.length, 500); // 渲染前500条保持极致流畅
            for (let i = 0; i < limit; i++) {
                const r = filtered[i];
                const tr = document.createElement("tr");
                const typeCls = getTypeBadgeClass(r.data_type);

                tr.innerHTML = `
                    <td style="text-align:center; color:#78909C;">${r.no}</td>
                    <td class="var-name">${escapeHtml(r.name)}</td>
                    <td><span class="badge-type ${typeCls}">${escapeHtml(r.data_type)}</span></td>
                    <td style="color:#37474F;">${escapeHtml(r.orig_comment || "(空)")}</td>
                    <td style="color:#004D40; font-weight:500;">${escapeHtml(r.delivered_comment || "(空)")}</td>
                    <td style="text-align:center;">${getStatusBadge(r.status)}</td>
                `;
                tbody.appendChild(tr);
            }

            if (filtered.length > 500) {
                const infoTr = document.createElement("tr");
                infoTr.innerHTML = `<td colspan="6" style="text-align:center; background:#ECEFF1; color:#546E7A; padding:8px;">已渲染前 500 行 (共 ${filtered.length} 行匹配)。可通过搜索框精确定位。</td>`;
                tbody.appendChild(infoTr);
            }
        }

        function escapeHtml(str) {
            if (!str) return "";
            return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }

        function log(msg, tag) {
            const c = document.getElementById("console");
            const div = document.createElement("div");
            div.textContent = msg;
            if (tag) div.className = "log-" + tag;
            c.appendChild(div);
            c.scrollTop = c.scrollHeight;
        }

        async function pollLogs() {
            try {
                const res = await fetch("/api/logs");
                const data = await res.json();
                const c = document.getElementById("console");
                c.innerHTML = "";
                data.logs.forEach(item => {
                    const div = document.createElement("div");
                    div.textContent = item.msg;
                    div.className = "log-" + item.tag;
                    c.appendChild(div);
                });
                c.scrollTop = c.scrollHeight;
            } catch(e) {}
            setTimeout(pollLogs, 1000);
        }

        async function runTurnkey(machineName) {
            log("\\n[WEB] 触发整机交付管线: " + machineName, "INFO");
            const res = await fetch("/api/turnkey?machine=" + encodeURIComponent(machineName), { method: "POST" });
            const data = await res.json();
            if (data.status === "ok") {
                alert(machineName + " 整机全量交付任务已提交！请在底部控制台查看实时执行进度。");
                setTimeout(refreshCurrentTable, 3000);
            } else {
                alert("执行失败: " + data.message);
            }
        }

        async function runVerify(machineName) {
            log("\\n[WEB] 触发质量验收: " + machineName, "INFO");
            const res = await fetch("/api/verify?machine=" + encodeURIComponent(machineName), { method: "POST" });
            const data = await res.json();
            alert(data.passed ? "100% 质量验收通过！" : "质检未通过，请核对日志！");
        }

        async function testTerm() {
            const text = document.getElementById("termInput").value;
            const lang = document.getElementById("inspectLang") ? document.getElementById("inspectLang").value : "en";
            const res = await fetch("/api/translate?text=" + encodeURIComponent(text) + "&lang=" + encodeURIComponent(lang));
            const data = await res.json();
            const langLabel = (data.lang === "it") ? "意文译文: " : "纯英文: ";
            document.getElementById("termOutput").textContent = langLabel + data.en + " | 规范中文: " + data.cn;
        }

        function setTerm(t) {
            document.getElementById("termInput").value = t;
            testTerm();
        }

        async function clearLogs() {
            await fetch("/api/clear-logs", { method: "POST" });
            document.getElementById("console").innerHTML = "";
        }

        // 初始化启动
        loadMachineList();
        pollLogs();
    </script>
</body>
</html>
"""

class WebConsoleHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ["/", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif parsed.path == "/api/logs":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            with LOG_LOCK:
                logs_copy = list(LOG_BUFFER)
            self.wfile.write(json.dumps({"logs": logs_copy}).encode("utf-8"))
        elif parsed.path == "/api/translate":
            qs = urllib.parse.parse_qs(parsed.query)
            text = qs.get("text", [""])[0]
            target_lang = qs.get("lang", ["en"])[0]
            kernel = toolkit.get_default_kernel()
            solar_plugin = find_plugin("solar_frame_dictionary_plugin.py")
            if os.path.exists(solar_plugin):
                try:
                    kernel.load_plugins_from_file(solar_plugin)
                except Exception:
                    pass
            engine = toolkit.IndustrialTermEngine(kernel=kernel)
            en = engine.translate(text, target_lang=target_lang)
            cn = engine.derive_chinese_comment(text, text)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"en": en, "cn": cn, "lang": target_lang}).encode("utf-8"))
        elif parsed.path == "/api/inspect/machines":
            ws_root = os.path.abspath(os.path.join(WORKFLOW_ROOT, ".."))
            machines = TableInspector.discover_machines(ws_root)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"machines": machines}, ensure_ascii=False).encode("utf-8"))
        elif parsed.path == "/api/inspect/tables":
            qs = urllib.parse.parse_qs(parsed.query)
            machine = qs.get("machine", ["3-修边机"])[0]
            m_root = find_machine_root(machine)
            tables = TableInspector.list_machine_available_tables(m_root)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"tables": tables, "machine_root": m_root}, ensure_ascii=False).encode("utf-8"))
        elif parsed.path == "/api/inspect/detail":
            qs = urllib.parse.parse_qs(parsed.query)
            machine = qs.get("machine", ["3-修边机"])[0]
            filename = qs.get("file", [""])[0]
            target_lang = qs.get("lang", ["en"])[0]
            m_root = find_machine_root(machine)
            tables = TableInspector.list_machine_available_tables(m_root)
            t_info = next((t for t in tables if t["file_name"] == filename), None)
            if t_info:
                src_path = t_info.get("src_path", "")
                tgt_path = t_info.get("target_path", "")
            else:
                src_path = os.path.join(m_root, "io注释_备份_原始留档", "变量表", filename)
                tgt_path = os.path.join(m_root, "变量表", filename)
            res = TableInspector.inspect_single_table(src_path, tgt_path)
            res_dict = res.to_dict()
            res_dict["platform"] = toolkit.detect_table_platform(src_path) if os.path.exists(src_path) else "unknown"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(res_dict, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/turnkey":
            qs = urllib.parse.parse_qs(parsed.query)
            machine = qs.get("machine", ["3-修边机"])[0]
            
            def run_job():
                try:
                    add_log(f"=======================================================", "INFO")
                    add_log(f"启动 {machine} 整机交钥匙交付与验收...", "INFO")
                    add_log(f"=======================================================", "INFO")
                    
                    m_root = find_machine_root(machine)
                    src_dir = os.path.join(m_root, "io注释_备份_原始留档", "变量表")
                    dst_en = os.path.join(m_root, "变量表")
                    dst_cn = os.path.join(m_root, "io注释_备份_规范中文版", "变量表")
                    md_path = os.path.join(dst_en, "变量表中英文对照表_Corning交付版.md")
                    
                    kernel = toolkit.get_default_kernel()
                    trimmer_plugin = find_plugin("trimmer_dictionary_plugin.py")
                    if os.path.exists(trimmer_plugin):
                        kernel.load_plugins_from_file(trimmer_plugin)

                    proc = toolkit.VarTableProcessor(mode="B", kernel=kernel)
                    raw_files = [f for f in sorted(os.listdir(src_dir)) if f.endswith('.csv') and not f.endswith('_new.csv')]
                    
                    all_recs = {}
                    for fname in raw_files:
                        sp = os.path.join(src_dir, fname)
                        ep = os.path.join(dst_en, fname)
                        cp = os.path.join(dst_cn, fname)
                        recs = proc.process_file(sp, ep, cp)
                        all_recs[fname] = recs
                        add_log(f"  -> 处理完成: {fname:24s} | {len(recs):5d} 行", "PASS")

                    add_log("正在导出整合中英对照总表 Markdown 交付报告...", "INFO")
                    proc.generate_markdown_report(all_recs, md_path, project_title=f"{machine} Corning Delivery")

                    add_log("启动自动化 5 重质量验收门禁...", "INFO")
                    all_passed = True
                    for fname in raw_files:
                        sp = os.path.join(src_dir, fname)
                        ep = os.path.join(dst_en, fname)
                        ok, errs = toolkit.TableVerifier.verify_file(sp, ep, mode="B", kernel=kernel)
                        if ok:
                            add_log(f"  [PASS] {fname:24s} | 100% 验收通过", "PASS")
                        else:
                            all_passed = False
                            add_log(f"  [FAIL] {fname:24s} | 异常: {errs}", "FAIL")

                    if all_passed:
                        add_log(f"FINAL RESULT: ALL {len(raw_files)} FILES PASSED 100% QUALITY CHECKS!", "PASS")
                except Exception as ex:
                    add_log(f"[ERROR] 执行异常: {str(ex)}", "FAIL")

            threading.Thread(target=run_job, daemon=True).start()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))

        elif parsed.path == "/api/verify":
            qs = urllib.parse.parse_qs(parsed.query)
            machine = qs.get("machine", ["3-修边机"])[0]
            m_root = find_machine_root(machine)
            src_dir = os.path.join(m_root, "io注释_备份_原始留档", "变量表")
            dst_en = os.path.join(m_root, "变量表")
            
            kernel = toolkit.get_default_kernel()
            passed = toolkit.TableVerifier.verify_directory(src_dir, dst_en, mode="B", kernel=kernel)
            add_log(f"验收执行完毕: {machine} -> {'全部通过' if passed else '检测到违例'}", "PASS" if passed else "FAIL")
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"passed": passed}).encode("utf-8"))

        elif parsed.path == "/api/clear-logs":
            with LOG_LOCK:
                LOG_BUFFER.clear()
            self.send_response(200)
            self.end_headers()


def start_server(port: int = 8989) -> None:
    server = HTTPServer(("127.0.0.1", port), WebConsoleHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"=====================================================================")
    print(f" Corning PLC Table Toolkit 本地 Web 控制台已启动!")
    print(f" 浏览器访问地址: {url}")
    print(f"=====================================================================")
    add_log(f"Web 控制台服务已就绪，地址: {url}", "INFO")
    
    # 自动在系统默认浏览器中打开
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。")


if __name__ == "__main__":
    port = 8989
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    start_server(port)
