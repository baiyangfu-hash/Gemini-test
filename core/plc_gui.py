# -*- coding: utf-8 -*-
"""
=============================================================================
PLC Table Toolkit - 工业级可视化图形界面 (Corning Standard GUI)
=============================================================================
特性：
  1. 零外部依赖：基于 Python 标准库 tkinter / ttk 开发，无需 pip 安装，开箱即用。
  2. 异步非阻塞：后台多线程执行大批量处理，界面流畅不卡顿，实时刷新进度与日志。
  3. 多维功能集成：
     - Tab 1: GVL 变量表批量与单文件处理（策略 B / 策略 A、中文规范版备份、Markdown 报告）
     - Tab 2: IO 注释表转换（软元件映射、多列/双列自动识别）
     - Tab 3: 自动化质量验收门禁（5 重严苛基线校验，可视化 PASS / FAIL 统计）
     - Tab 4: 整机一键交钥匙交付（机台级批量自动化、交付总表与质检一体化）
     - Tab 5: 工业术语沙盒测验（实时输入中文注释，即时预览纯英文翻译效果）
"""

import os
import sys
import re
import queue
import threading
import subprocess
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from typing import Optional, List, Dict, Tuple, Any

# Ensure current directory, workflow root and plugins are in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_ROOT = os.path.dirname(CURRENT_DIR)
for p in [CURRENT_DIR, WORKFLOW_ROOT, os.path.join(WORKFLOW_ROOT, "plugins")]:
    if p not in sys.path:
        sys.path.insert(0, p)

if getattr(sys, 'frozen', False):
    EXE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    BUNDLE_DIR = getattr(sys, '_MEIPASS', EXE_DIR)
else:
    EXE_DIR = CURRENT_DIR
    BUNDLE_DIR = CURRENT_DIR

def get_bundle_resource(rel_path: str) -> str:
    """获取内嵌资源、同级资源或规范子目录资源绝对路径 (兼容 PyInstaller 与源码运行)"""
    candidates = [
        os.path.join(BUNDLE_DIR, rel_path),
        os.path.join(EXE_DIR, rel_path),
        os.path.join(CURRENT_DIR, rel_path),
        os.path.join(WORKFLOW_ROOT, rel_path),
        os.path.join(WORKFLOW_ROOT, "docs", rel_path),
        os.path.join(WORKFLOW_ROOT, "plugins", rel_path),
        os.path.join(EXE_DIR, "plugins", rel_path),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]

import plc_table_toolkit as toolkit
from table_inspector import TableInspector


class StdoutRedirector:
    """线程安全的控制台日志重定向器"""
    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue

    def write(self, text: str) -> None:
        if text:
            self.log_queue.put(text)

    def flush(self) -> None:
        pass


class PLCToolkitGUI:
    """工业级 PLC 表格工具套件主 GUI 应用"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Corning PLC 变量表与 IO 注释规范化套件 (Corning Toolkit v2.0)")
        self.root.geometry("1020x760")
        self.root.minsize(880, 640)

        # 默认工作根目录智能探测 (优先寻找 康宁 目录)
        cand1 = os.path.abspath(os.path.join(WORKFLOW_ROOT, ".."))
        cand2 = WORKFLOW_ROOT
        cand3 = os.path.abspath(os.path.join(EXE_DIR, ".."))
        cand4 = os.path.abspath(os.path.join(EXE_DIR, "..", ".."))

        for cand in [cand1, cand2, cand3, cand4]:
            if os.path.exists(os.path.join(cand, "康宁")):
                self.default_workspace = cand
                break
        else:
            self.default_workspace = r"c:\Users\fubai\Documents\BaiduSyncdisk\项目\CT173-美国康宁-6月-付白杨\PLC+HMI程序"

        self.machine3_dir = os.path.join(self.default_workspace, "康宁", "3-修边机")

        # 线程与日志队列
        self.log_queue: queue.Queue = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None

        # 初始化微内核与检视器缓存
        self.kernel = toolkit.get_default_kernel()
        self.trimmer_plugin_path = get_bundle_resource("trimmer_dictionary_plugin.py")
        self.solar_frame_plugin_path = get_bundle_resource("solar_frame_dictionary_plugin.py")
        if os.path.exists(self.trimmer_plugin_path):
            try:
                self.kernel.load_plugins_from_file(self.trimmer_plugin_path)
            except Exception as e:
                pass
        if os.path.exists(self.solar_frame_plugin_path):
            try:
                self.kernel.load_plugins_from_file(self.solar_frame_plugin_path)
            except Exception as e:
                pass
        self.inspector_records: List[Any] = []

        # 设置 ttk 现代化样式
        self._init_styles()

        # 构建主界面布局
        self._build_ui()

        # 启动日志轮询定时器
        self.root.after(100, self._poll_log_queue)

    def _init_styles(self) -> None:
        """配置 TTK 界面主题与配色"""
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        # 基础配色定义 (Corning Blue / Industrial Slate)
        self.COLOR_BG = "#F4F6F9"
        self.COLOR_PANEL = "#FFFFFF"
        self.COLOR_PRIMARY = "#005691"
        self.COLOR_PRIMARY_HOVER = "#004070"
        self.COLOR_SUCCESS = "#2E7D32"
        self.COLOR_ERROR = "#C62828"
        self.COLOR_TEXT = "#263238"

        self.root.configure(bg=self.COLOR_BG)

        style.configure("TFrame", background=self.COLOR_BG)
        style.configure("Card.TFrame", background=self.COLOR_PANEL, relief="ridge", borderwidth=1)
        style.configure("TLabel", background=self.COLOR_BG, foreground=self.COLOR_TEXT, font=("Segoe UI", 9))
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground=self.COLOR_PRIMARY)
        style.configure("SubHeader.TLabel", font=("Segoe UI", 9, "bold"), foreground="#455A64")
        style.configure("Status.TLabel", font=("Segoe UI", 9), foreground="#37474F")
        style.configure("Success.TLabel", font=("Segoe UI", 10, "bold"), foreground=self.COLOR_SUCCESS)
        style.configure("Error.TLabel", font=("Segoe UI", 10, "bold"), foreground=self.COLOR_ERROR)

        style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), background=self.COLOR_PRIMARY, foreground="#FFFFFF")
        style.map("Primary.TButton", background=[("active", self.COLOR_PRIMARY_HOVER)])

        style.configure("Success.TButton", font=("Segoe UI", 9, "bold"), background=self.COLOR_SUCCESS, foreground="#FFFFFF")
        style.configure("Action.TButton", font=("Segoe UI", 9))

    def _build_ui(self) -> None:
        """构建主窗口结构"""
        # 1. 顶部标题栏
        top_bar = tk.Frame(self.root, bg=self.COLOR_PRIMARY, height=56)
        top_bar.pack(side=tk.TOP, fill=tk.X)

        title_lbl = tk.Label(
            top_bar,
            text="CORNING PLC 表格规范化与翻译套件 (Microkernel Edition)",
            font=("Segoe UI", 13, "bold"),
            bg=self.COLOR_PRIMARY,
            fg="#FFFFFF"
        )
        title_lbl.pack(side=tk.LEFT, padx=16, pady=10)

        badge_lbl = tk.Label(
            top_bar,
            text="GUI / CLI / API / SPI 四位一体",
            font=("Segoe UI", 8),
            bg="#003D66",
            fg="#E0E0E0",
            padx=8,
            pady=3
        )
        badge_lbl.pack(side=tk.RIGHT, padx=12)

        # 顶部嵌入式文档与 Web 控制台快捷入口
        btn_box = tk.Frame(top_bar, bg=self.COLOR_PRIMARY)
        btn_box.pack(side=tk.RIGHT, padx=4)

        tk.Button(
            btn_box, text="📖 操作手册", font=("Segoe UI", 8), bg="#004070", fg="#FFFFFF",
            relief="flat", cursor="hand2", padx=6, pady=2,
            command=lambda: self._open_doc("README_工作流使用说明.md")
        ).pack(side=tk.LEFT, padx=3)

        tk.Button(
            btn_box, text="🏛️ 架构白皮书", font=("Segoe UI", 8), bg="#004070", fg="#FFFFFF",
            relief="flat", cursor="hand2", padx=6, pady=2,
            command=lambda: self._open_doc("ARCHITECTURE_AND_EXTENSIBILITY.md")
        ).pack(side=tk.LEFT, padx=3)

        tk.Button(
            btn_box, text="🌐 切换Web端", font=("Segoe UI", 8, "bold"), bg="#2E7D32", fg="#FFFFFF",
            relief="flat", cursor="hand2", padx=6, pady=2,
            command=self._open_web_console
        ).pack(side=tk.LEFT, padx=3)

        # 2. 中部选项卡容器 (Notebook)
        main_container = ttk.Frame(self.root, padding=10)
        main_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 构建各个子功能选项卡
        self.tab_vars = ttk.Frame(self.notebook, padding=12)
        self.tab_io = ttk.Frame(self.notebook, padding=12)
        self.tab_verify = ttk.Frame(self.notebook, padding=12)
        self.tab_turnkey = ttk.Frame(self.notebook, padding=12)
        self.tab_tester = ttk.Frame(self.notebook, padding=12)
        self.tab_inspector = ttk.Frame(self.notebook, padding=12)

        self.notebook.add(self.tab_inspector, text=" 📊 变量与文档对照查看 ")
        self.notebook.add(self.tab_vars, text=" 📋 GVL 变量表批处理 ")
        self.notebook.add(self.tab_io, text=" 🔌 IO 注释表转换 ")
        self.notebook.add(self.tab_verify, text=" ✅ 质量验收门禁 ")
        self.notebook.add(self.tab_turnkey, text=" 🏭 整机一键交付 ")
        self.notebook.add(self.tab_tester, text=" 🔍 术语翻译测验 ")

        self._build_tab_inspector()
        self._build_tab_vars()
        self._build_tab_io()
        self._build_tab_verify()
        self._build_tab_turnkey()
        self._build_tab_tester()

        # 3. 底部实时执行监控与控制台
        self._build_bottom_monitor()

    # =========================================================================
    # TAB 0: 变量与文档只读对比检视器 (TableInspector)
    # =========================================================================
    def _build_tab_inspector(self) -> None:
        pane = self.tab_inspector

        # 顶部操作工具栏卡片
        ctrl_card = ttk.LabelFrame(pane, text="数据源与过滤条件 (纯只读安全模式)", padding=10)
        ctrl_card.pack(fill=tk.X, pady=(0, 6))

        row0 = ttk.Frame(ctrl_card)
        row0.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(row0, text="PLC 品牌/平台:").pack(side=tk.LEFT, padx=(0, 4))
        self.platform_var = tk.StringVar(value="⚡ 自动智能识别 (Auto Detect)")
        self.platform_cb = ttk.Combobox(
            row0, textvariable=self.platform_var,
            values=[
                "⚡ 自动智能识别 (Auto Detect)",
                "汇川 AutoShop (H3U/H5U 小型PLC)",
                "汇川 InoProShop (CODESYS/AM/AC 中大型PLC)",
                "三菱 GX Works3 (iQ-R/iQ-F 平台)"
            ],
            state="readonly", width=34
        )
        self.platform_cb.pack(side=tk.LEFT, padx=(0, 12))
        self.platform_cb.bind("<<ComboboxSelected>>", lambda e: self._on_platform_changed())

        ttk.Label(row0, text="目标交付语言:").pack(side=tk.LEFT, padx=(0, 4))
        self.target_lang_var = tk.StringVar(value="English (纯英文交付)")
        self.target_lang_cb = ttk.Combobox(
            row0, textvariable=self.target_lang_var,
            values=["English (纯英文交付)", "Italiano (意大利语交付)"],
            state="readonly", width=22
        )
        self.target_lang_cb.pack(side=tk.LEFT, padx=(0, 4))
        self.target_lang_cb.bind("<<ComboboxSelected>>", lambda e: self._on_inspect_table_changed())

        row1 = ttk.Frame(ctrl_card)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text="选择机台:").pack(side=tk.LEFT, padx=(0, 4))
        self.inspect_machine_var = tk.StringVar()
        self.machine_path_map: Dict[str, str] = {}
        self.inspect_machine_cb = ttk.Combobox(
            row1, textvariable=self.inspect_machine_var,
            state="readonly", width=14
        )
        self.inspect_machine_cb.pack(side=tk.LEFT, padx=(0, 4))
        self.inspect_machine_cb.bind("<<ComboboxSelected>>", lambda e: self._on_inspect_machine_changed())

        ttk.Button(row1, text="📁 浏览机台...", command=self._browse_custom_machine).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row1, text="选择变量表:").pack(side=tk.LEFT, padx=(0, 4))
        self.inspect_table_var = tk.StringVar()
        self.inspect_table_cb = ttk.Combobox(row1, textvariable=self.inspect_table_var, state="readonly", width=26)
        self.inspect_table_cb.pack(side=tk.LEFT, padx=(0, 10))
        self.inspect_table_cb.bind("<<ComboboxSelected>>", lambda e: self._on_inspect_table_changed())

        ttk.Label(row1, text="实时搜索:").pack(side=tk.LEFT, padx=(0, 4))
        self.inspect_search_var = tk.StringVar()
        search_entry = ttk.Entry(row1, textvariable=self.inspect_search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        search_entry.bind("<KeyRelease>", lambda e: self._filter_treeview())

        ttk.Button(row1, text="🔄 刷新", command=self._on_inspect_table_changed).pack(side=tk.RIGHT)

        # 状态概览栏
        self.inspect_status_lbl = ttk.Label(
            pane, text="总变量数: - | 数据类型统计: - | 状态: 就绪",
            font=("Segoe UI", 9, "bold"), foreground=self.COLOR_PRIMARY
        )
        self.inspect_status_lbl.pack(fill=tk.X, pady=(0, 6))

        # 中部表格区域 (Treeview + 垂直滚动条)
        tree_frame = ttk.Frame(pane)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("no", "name", "type", "orig", "deliv", "status")
        self.inspect_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self.inspect_tree.heading("no", text="序号", anchor=tk.CENTER)
        self.inspect_tree.heading("name", text="变量名 (Variable Name)", anchor=tk.W)
        self.inspect_tree.heading("type", text="数据类型 (DataType)", anchor=tk.W)
        self.inspect_tree.heading("orig", text="原始文档 (中文注释)", anchor=tk.W)
        self.inspect_tree.heading("deliv", text="变更后文档 (纯英文交付)", anchor=tk.W)
        self.inspect_tree.heading("status", text="状态", anchor=tk.CENTER)

        self.inspect_tree.column("no", width=50, stretch=False, anchor=tk.CENTER)
        self.inspect_tree.column("name", width=180, stretch=False)
        self.inspect_tree.column("type", width=120, stretch=False)
        self.inspect_tree.column("orig", width=250, stretch=True)
        self.inspect_tree.column("deliv", width=270, stretch=True)
        self.inspect_tree.column("status", width=80, stretch=False, anchor=tk.CENTER)

        # 状态标签着色
        self.inspect_tree.tag_configure("translated", foreground="#1B5E20")
        self.inspect_tree.tag_configure("derived", foreground="#E65100")
        self.inspect_tree.tag_configure("alert", foreground="#C62828")
        self.inspect_tree.tag_configure("unchanged", foreground="#546E7A")

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.inspect_tree.yview)
        self.inspect_tree.configure(yscrollcommand=v_scroll.set)

        self.inspect_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.inspect_tree.bind("<Double-1>", self._on_tree_double_click)

        # 延迟 200ms 动态发现机台并初始化加载变量表
        self.root.after(200, self._init_machine_list)

    def _init_machine_list(self) -> None:
        """动态发现并初始化机台列表 (支持 康宁 目录及工作区内任意机台子目录)"""
        machines = TableInspector.discover_machines(self.default_workspace)
        self.machine_path_map = {m["name"]: m["path"] for m in machines}
        names = list(self.machine_path_map.keys())
        self.inspect_machine_cb["values"] = names
        if names:
            # 优先自动选择 3-修边机 或列表第 1 个机台
            default_choice = "3-修边机" if "3-修边机" in names else names[0]
            self.inspect_machine_cb.set(default_choice)
            self._on_inspect_machine_changed()
        else:
            self.inspect_machine_cb.set("")
            self.inspect_status_lbl.configure(text="未在当前工作空间检测到机台目录，可点击【📁 浏览机台...】手动选取任意文件夹")

    def _browse_custom_machine(self) -> None:
        """用户手动选择任意外部/自定义机台文件夹 (支持任意磁盘路径、网络共享或客户项目)"""
        selected = filedialog.askdirectory(initialdir=self.default_workspace, title="选择机台根目录")
        if selected:
            selected_norm = os.path.normpath(selected)
            m_name = os.path.basename(selected_norm)
            label = f"[外部] {m_name}"
            self.machine_path_map[label] = selected_norm
            vals = list(self.inspect_machine_cb["values"])
            if label not in vals:
                vals.append(label)
                self.inspect_machine_cb["values"] = vals
            self.inspect_machine_cb.set(label)
            self._on_inspect_machine_changed()

    def _on_inspect_machine_changed(self) -> None:
        m_name = self.inspect_machine_var.get()
        if not m_name:
            return
        m_dir = self.machine_path_map.get(m_name)
        if not m_dir or not os.path.exists(m_dir):
            m_dir = os.path.join(self.default_workspace, "康宁", m_name)

        tables = TableInspector.list_machine_available_tables(m_dir)
        self.current_machine_tables = {t["file_name"]: t for t in tables}
        names = [t["file_name"] for t in tables]
        self.inspect_table_cb["values"] = names
        if names:
            self.inspect_table_cb.current(0)
            self._on_inspect_table_changed()
        else:
            self.inspect_table_var.set("")
            self.inspect_tree.delete(*self.inspect_tree.get_children())
            self.inspect_status_lbl.configure(text=f"机台 [{m_name}] 目录下未找到变量表文件")

    def _get_selected_platform(self) -> str:
        val = self.platform_var.get()
        if "AutoShop" in val:
            return "autoshop"
        if "InoProShop" in val:
            return "inoproshop"
        if "三菱" in val or "GX Works3" in val:
            return "mitsubishi"
        return "auto"

    def _get_selected_target_lang(self) -> str:
        val = self.target_lang_var.get()
        if "Italiano" in val:
            return "it"
        return "en"

    def _on_platform_changed(self) -> None:
        self._on_inspect_table_changed()

    def _on_inspect_table_changed(self) -> None:
        f_name = self.inspect_table_var.get()
        if not f_name:
            return

        table_info = getattr(self, "current_machine_tables", {}).get(f_name)
        if table_info:
            src_path = table_info.get("src_path", "")
            tgt_path = table_info.get("target_path", "")
        else:
            m_name = self.inspect_machine_var.get()
            m_dir = self.machine_path_map.get(m_name, os.path.join(self.default_workspace, "康宁", m_name))
            src_path = os.path.join(m_dir, "io注释_备份_原始留档", "变量表", f_name)
            tgt_path = os.path.join(m_dir, "变量表", f_name)

        res = TableInspector.inspect_single_table(src_path, tgt_path)
        self.inspector_records = res.records

        # 整理类型分布摘要
        type_str = ", ".join([f"{k}:{v}" for k, v in list(res.type_breakdown.items())[:5]])
        pe_status = "⚠️ 发现未翻译中文!" if res.has_chinese_residue else "✅ 交付注释 0 中文残留 (100% Pure English)"
        plat = self._get_selected_platform()
        lang = self._get_selected_target_lang()
        detected_plat = toolkit.detect_table_platform(src_path) if os.path.exists(src_path) else "unknown"

        if plat == "mitsubishi" or (plat == "auto" and detected_plat == "mitsubishi"):
            plat_disp = "三菱 GX Works3"
        elif plat == "inoproshop" or (plat == "auto" and detected_plat == "inoproshop"):
            plat_disp = "汇川 InoProShop (CODESYS)"
        elif plat == "autoshop" or (plat == "auto" and detected_plat in ["autoshop", "inovance"]):
            plat_disp = "汇川 AutoShop (小型PLC)"
        else:
            plat_disp = "通用/自动识别"

        lang_disp = "Italiano" if lang == "it" else "English"
        self.inspect_status_lbl.configure(
            text=f"表格: {f_name} | 平台: {plat_disp} | 语种: {lang_disp} | 变量数: {res.total_rows} | 类型分布: {type_str} | {pe_status}"
        )

        self._filter_treeview()

    def _filter_treeview(self) -> None:
        q = self.inspect_search_var.get().strip().lower()
        self.inspect_tree.delete(*self.inspect_tree.get_children())

        st_map = {
            "translated": "🟢 已翻译",
            "derived": "🟡 智能推导",
            "alert": "⚠️ 中文残留",
            "unchanged": "⚪ 未变更"
        }

        count = 0
        for r in self.inspector_records:
            if q:
                match = (q in r.name.lower() or
                         q in r.data_type.lower() or
                         q in r.orig_comment.lower() or
                         q in r.delivered_comment.lower())
                if not match:
                    continue

            tag = r.status if r.status in ["translated", "derived", "alert"] else "unchanged"
            self.inspect_tree.insert(
                "", tk.END,
                values=(r.no, r.name, r.data_type, r.orig_comment or "(空)", r.delivered_comment or "(空)", st_map.get(r.status, "未变更")),
                tags=(tag,)
            )
            count += 1
            if count >= 800:
                break

    def _on_tree_double_click(self, event) -> None:
        item_id = self.inspect_tree.focus()
        if not item_id:
            return
        vals = self.inspect_tree.item(item_id, "values")
        if vals:
            msg = (
                f"【序号】: {vals[0]}\n"
                f"【变量名】: {vals[1]}\n"
                f"【数据类型】: {vals[2]}\n\n"
                f"【原始文档 (中文)】:\n{vals[3]}\n\n"
                f"【变更交付文档 (英文)】:\n{vals[4]}\n\n"
                f"【变更状态】: {vals[5]}"
            )
            messagebox.showinfo("变量与文档明细详情", msg)

    # =========================================================================
    # TAB 1: GVL 变量表处理
    # =========================================================================
    def _build_tab_vars(self) -> None:
        pane = self.tab_vars

        # 路径配置卡片
        card_paths = ttk.LabelFrame(pane, text="路径与数据源配置", padding=10)
        card_paths.pack(fill=tk.X, pady=(0, 10))

        # 源目录 / 源文件
        r1 = ttk.Frame(card_paths)
        r1.pack(fill=tk.X, pady=4)
        ttk.Label(r1, text="变量表源目录:", width=14).pack(side=tk.LEFT)
        self.var_src_var = tk.StringVar(value=os.path.join(self.machine3_dir, "io注释_备份_原始留档", "变量表"))
        ttk.Entry(r1, textvariable=self.var_src_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r1, text="选择目录...", command=lambda: self._browse_dir(self.var_src_var)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(r1, text="选择单文件...", command=lambda: self._browse_file(self.var_src_var)).pack(side=tk.RIGHT, padx=2)

        # 英文交付目录
        r2 = ttk.Frame(card_paths)
        r2.pack(fill=tk.X, pady=4)
        ttk.Label(r2, text="英文交付目录:", width=14).pack(side=tk.LEFT)
        self.var_en_var = tk.StringVar(value=os.path.join(self.machine3_dir, "变量表"))
        ttk.Entry(r2, textvariable=self.var_en_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r2, text="选择目录...", command=lambda: self._browse_dir(self.var_en_var)).pack(side=tk.RIGHT, padx=2)

        # 中文规范留档目录
        r3 = ttk.Frame(card_paths)
        r3.pack(fill=tk.X, pady=4)
        self.var_cn_enable = tk.BooleanVar(value=True)
        ttk.Checkbutton(r3, text="规范中文备份:", variable=self.var_cn_enable, width=14).pack(side=tk.LEFT)
        self.var_cn_var = tk.StringVar(value=os.path.join(self.machine3_dir, "io注释_备份_规范中文版", "变量表"))
        ttk.Entry(r3, textvariable=self.var_cn_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r3, text="选择目录...", command=lambda: self._browse_dir(self.var_cn_var)).pack(side=tk.RIGHT, padx=2)

        # Markdown 总表导出路径
        r4 = ttk.Frame(card_paths)
        r4.pack(fill=tk.X, pady=4)
        self.var_md_enable = tk.BooleanVar(value=True)
        ttk.Checkbutton(r4, text="生成中英对照表:", variable=self.var_md_enable, width=14).pack(side=tk.LEFT)
        self.var_md_var = tk.StringVar(value=os.path.join(self.machine3_dir, "变量表", "变量表中英文对照表_Corning交付版.md"))
        ttk.Entry(r4, textvariable=self.var_md_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r4, text="另存为...", command=lambda: self._browse_save_file(self.var_md_var, "*.md")).pack(side=tk.RIGHT, padx=2)

        # 策略与插件卡片
        card_opts = ttk.LabelFrame(pane, text="处理策略与扩展插件", padding=10)
        card_opts.pack(fill=tk.X, pady=(0, 10))

        ro1 = ttk.Frame(card_opts)
        ro1.pack(fill=tk.X, pady=2)
        ttk.Label(ro1, text="翻译策略:", width=12).pack(side=tk.LEFT)
        self.var_mode_var = tk.StringVar(value="B")
        ttk.Radiobutton(ro1, text="策略 B (推荐: 变量名 100% 保持不动，注释翻译为纯英文)", variable=self.var_mode_var, value="B").pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(ro1, text="策略 A (变量名蛇形英文，注释纯英文)", variable=self.var_mode_var, value="A").pack(side=tk.LEFT, padx=6)

        ro2 = ttk.Frame(card_opts)
        ro2.pack(fill=tk.X, pady=4)
        ttk.Label(ro2, text="领域插件注入:", width=12).pack(side=tk.LEFT)
        self.var_trimmer_plugin_enable = tk.BooleanVar(value=True)
        ttk.Checkbutton(ro2, text="挂载修边机专有术语插件 (trimmer_dictionary_plugin.py)", variable=self.var_trimmer_plugin_enable).pack(side=tk.LEFT, padx=6)

        # 动作按钮栏
        act_bar = ttk.Frame(pane)
        act_bar.pack(fill=tk.X, pady=6)
        self.btn_run_vars = ttk.Button(act_bar, text="🚀 开始批量翻译与规范化", style="Primary.TButton", command=self._start_process_vars)
        self.btn_run_vars.pack(side=tk.LEFT, padx=4, ipady=4)

        ttk.Button(act_bar, text="📂 打开交付目录", command=lambda: self._open_dir(self.var_en_var.get())).pack(side=tk.LEFT, padx=4)
        ttk.Button(act_bar, text="📄 打开中英对照报告", command=lambda: self._open_file(self.var_md_var.get())).pack(side=tk.LEFT, padx=4)

    # =========================================================================
    # TAB 2: IO 注释表转换
    # =========================================================================
    def _build_tab_io(self) -> None:
        pane = self.tab_io

        card_paths = ttk.LabelFrame(pane, text="IO 注释表转换配置", padding=10)
        card_paths.pack(fill=tk.X, pady=(0, 10))

        # 源 IO CSV
        r1 = ttk.Frame(card_paths)
        r1.pack(fill=tk.X, pady=4)
        ttk.Label(r1, text="源 IO 注释表:", width=14).pack(side=tk.LEFT)
        self.io_src_var = tk.StringVar(value="")
        ttk.Entry(r1, textvariable=self.io_src_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r1, text="选择文件...", command=lambda: self._browse_file(self.io_src_var, "*.csv")).pack(side=tk.RIGHT, padx=2)

        # 交付输出 IO CSV
        r2 = ttk.Frame(card_paths)
        r2.pack(fill=tk.X, pady=4)
        ttk.Label(r2, text="纯英文交付路径:", width=14).pack(side=tk.LEFT)
        self.io_dst_en_var = tk.StringVar(value="")
        ttk.Entry(r2, textvariable=self.io_dst_en_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r2, text="另存为...", command=lambda: self._browse_save_file(self.io_dst_en_var, "*.csv")).pack(side=tk.RIGHT, padx=2)

        # 规范中文留档 IO CSV
        r3 = ttk.Frame(card_paths)
        r3.pack(fill=tk.X, pady=4)
        self.io_dst_cn_enable = tk.BooleanVar(value=True)
        ttk.Checkbutton(r3, text="中文规范留档:", variable=self.io_dst_cn_enable, width=14).pack(side=tk.LEFT)
        self.io_dst_cn_var = tk.StringVar(value="")
        ttk.Entry(r3, textvariable=self.io_dst_cn_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r3, text="另存为...", command=lambda: self._browse_save_file(self.io_dst_cn_var, "*.csv")).pack(side=tk.RIGHT, padx=2)

        # 动作按钮
        act_bar = ttk.Frame(pane)
        act_bar.pack(fill=tk.X, pady=6)
        self.btn_run_io = ttk.Button(act_bar, text="⚡ 开始转换 IO 表", style="Primary.TButton", command=self._start_process_io)
        self.btn_run_io.pack(side=tk.LEFT, padx=4, ipady=4)
        ttk.Button(act_bar, text="📂 打开输出目录", command=lambda: self._open_dir_of_file(self.io_dst_en_var.get())).pack(side=tk.LEFT, padx=4)

    # =========================================================================
    # TAB 3: 自动化质量验收门禁
    # =========================================================================
    def _build_tab_verify(self) -> None:
        pane = self.tab_verify

        card = ttk.LabelFrame(pane, text="质量验收门禁配置 (5-Fold Checks)", padding=10)
        card.pack(fill=tk.X, pady=(0, 10))

        # 待测交付目录
        r1 = ttk.Frame(card)
        r1.pack(fill=tk.X, pady=4)
        ttk.Label(r1, text="待检测交付目录:", width=14).pack(side=tk.LEFT)
        self.ver_target_var = tk.StringVar(value=os.path.join(self.machine3_dir, "变量表"))
        ttk.Entry(r1, textvariable=self.ver_target_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r1, text="选择目录...", command=lambda: self._browse_dir(self.ver_target_var)).pack(side=tk.RIGHT, padx=2)

        # 原始基准目录 (用于行数对齐校验)
        r2 = ttk.Frame(card)
        r2.pack(fill=tk.X, pady=4)
        ttk.Label(r2, text="原始基准留档目录:", width=14).pack(side=tk.LEFT)
        self.ver_src_var = tk.StringVar(value=os.path.join(self.machine3_dir, "io注释_备份_原始留档", "变量表"))
        ttk.Entry(r2, textvariable=self.ver_src_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r2, text="选择目录...", command=lambda: self._browse_dir(self.ver_src_var)).pack(side=tk.RIGHT, padx=2)

        # 校验选项
        r3 = ttk.Frame(card)
        r3.pack(fill=tk.X, pady=4)
        ttk.Label(r3, text="表格类型:", width=14).pack(side=tk.LEFT)
        self.ver_type_var = tk.StringVar(value="var")
        ttk.Radiobutton(r3, text="GVL 变量表 (9列格式保真 / CRLF / 0中文残留)", variable=self.ver_type_var, value="var").pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(r3, text="IO 硬件表", variable=self.ver_type_var, value="io").pack(side=tk.LEFT, padx=6)

        # 验收按钮
        act_bar = ttk.Frame(pane)
        act_bar.pack(fill=tk.X, pady=6)
        self.btn_run_verify = ttk.Button(act_bar, text="🛡️ 启动 5 重严苛质量验收", style="Primary.TButton", command=self._start_verify)
        self.btn_run_verify.pack(side=tk.LEFT, padx=4, ipady=4)

    # =========================================================================
    # TAB 4: 整机一键交钥匙交付
    # =========================================================================
    def _build_tab_turnkey(self) -> None:
        pane = self.tab_turnkey

        card = ttk.LabelFrame(pane, text="整机一键交付流水线 (Turnkey Pipeline)", padding=10)
        card.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            card,
            text="整机交付流水线将自动完成：\n"
                 "1. 扫描机台原始留档目录全部 GVL 变量表 (自动识别 12 个基准表)\n"
                 "2. 按照策略 B 执行纯英文翻译与转义清洗 (GBK/CRLF 保真)\n"
                 "3. 自动生成规范中文留档表 (供国内售后与版本溯源)\n"
                 "4. 生成带文首交互式目录与双向锚点的单一整合 Markdown 总表\n"
                 "5. 启动 5 重自动化严苛质量验收，确保 100% 达到康宁验收标准",
            justify=tk.LEFT,
            foreground="#37474F"
        ).pack(anchor=tk.W, pady=6)

        r1 = ttk.Frame(card)
        r1.pack(fill=tk.X, pady=6)
        ttk.Label(r1, text="机台根目录:", width=12, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.turnkey_dir_var = tk.StringVar(value=self.machine3_dir)
        ttk.Entry(r1, textvariable=self.turnkey_dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r1, text="选择机台目录...", command=lambda: self._browse_dir(self.turnkey_dir_var)).pack(side=tk.RIGHT, padx=2)

        # 快捷切换预设机台
        presets_bar = ttk.Frame(card)
        presets_bar.pack(fill=tk.X, pady=4)
        ttk.Label(presets_bar, text="快速预设机台:", width=12).pack(side=tk.LEFT)

        m1_path = os.path.join(self.default_workspace, "康宁", "1-封边机")
        m2_path = os.path.join(self.default_workspace, "康宁", "2-撕胶带机")
        m3_path = os.path.join(self.default_workspace, "康宁", "3-修边机")

        ttk.Button(presets_bar, text="1-封边机", command=lambda: self.turnkey_dir_var.set(m1_path)).pack(side=tk.LEFT, padx=3)
        ttk.Button(presets_bar, text="2-撕胶带机", command=lambda: self.turnkey_dir_var.set(m2_path)).pack(side=tk.LEFT, padx=3)
        ttk.Button(presets_bar, text="3-修边机", command=lambda: self.turnkey_dir_var.set(m3_path)).pack(side=tk.LEFT, padx=3)

        act_bar = ttk.Frame(pane)
        act_bar.pack(fill=tk.X, pady=10)
        self.btn_run_turnkey = ttk.Button(act_bar, text="🌟 一键整机全流程交付与验收", style="Primary.TButton", command=self._start_turnkey)
        self.btn_run_turnkey.pack(side=tk.LEFT, padx=4, ipady=6)

        ttk.Button(act_bar, text="📂 打开机台交付目录", command=lambda: self._open_dir(os.path.join(self.turnkey_dir_var.get(), "变量表"))).pack(side=tk.LEFT, padx=4)

    # =========================================================================
    # TAB 5: 工业术语沙盒测验
    # =========================================================================
    def _build_tab_tester(self) -> None:
        pane = self.tab_tester

        card = ttk.LabelFrame(pane, text="工业电气与机械术语即时翻译沙盒", padding=10)
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        ttk.Label(card, text="在下方输入工业注释、PLC 变量名或中英混杂语句，测试微内核多阶段级联翻译结果:").pack(anchor=tk.W, pady=4)

        in_frame = ttk.Frame(card)
        in_frame.pack(fill=tk.X, pady=4)
        ttk.Label(in_frame, text="输入中文/注释:", width=14).pack(side=tk.LEFT)
        self.tester_in_var = tk.StringVar(value="伺服原点门型光电检测异常，曲线类型：0，T型；1，S型")
        in_entry = ttk.Entry(in_frame, textvariable=self.tester_in_var, font=("Consolas", 10))
        in_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        in_entry.bind("<Return>", lambda e: self._do_term_test())
        ttk.Button(in_frame, text="🔍 立即翻译", style="Primary.TButton", command=self._do_term_test).pack(side=tk.RIGHT)

        out_frame = ttk.Frame(card)
        out_frame.pack(fill=tk.X, pady=4)
        ttk.Label(out_frame, text="纯英文交付输出:", width=14).pack(side=tk.LEFT)
        self.tester_out_var = tk.StringVar()
        ttk.Entry(out_frame, textvariable=self.tester_out_var, font=("Consolas", 10, "bold"), state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        cn_frame = ttk.Frame(card)
        cn_frame.pack(fill=tk.X, pady=4)
        ttk.Label(cn_frame, text="中文规范推导:", width=14).pack(side=tk.LEFT)
        self.tester_cn_var = tk.StringVar()
        ttk.Entry(cn_frame, textvariable=self.tester_cn_var, font=("Consolas", 10), state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        # 示例词条快捷点击测试
        quick_frame = ttk.LabelFrame(card, text="预设工业术语样例 (点击即测试)", padding=6)
        quick_frame.pack(fill=tk.X, pady=8)

        samples = [
            "修边刀上升到位",
            "旋转角度：90°",
            "温度设定：25℃",
            "伺服报警！（严重）",
            "PLCOpen状态机，故障停机",
            "配方地址变址寄存器",
            "四角吸盘气缸上升到位"
        ]

        row_box = ttk.Frame(quick_frame)
        row_box.pack(fill=tk.X)
        for s in samples:
            ttk.Button(row_box, text=s, command=lambda text=s: self._set_and_test_term(text)).pack(side=tk.LEFT, padx=3, pady=2)

    def _set_and_test_term(self, text: str) -> None:
        self.tester_in_var.set(text)
        self._do_term_test()

    def _do_term_test(self) -> None:
        src = self.tester_in_var.get().strip()
        if not src:
            return
        engine = toolkit.IndustrialTermEngine(kernel=self.kernel)
        en = engine.translate(src)
        cn = engine.derive_chinese_comment(src, src)
        self.tester_out_var.set(en)
        self.tester_cn_var.set(cn)

    # =========================================================================
    # 底部监控与日志控制台
    # =========================================================================
    def _build_bottom_monitor(self) -> None:
        bot_frame = ttk.Frame(self.root, padding=10)
        bot_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        # 状态指示与进度条
        stat_bar = ttk.Frame(bot_frame)
        stat_bar.pack(fill=tk.X, pady=(0, 4))

        self.lbl_status = ttk.Label(stat_bar, text="就绪 - 等待用户操作", style="Status.TLabel")
        self.lbl_status.pack(side=tk.LEFT)

        self.progress_bar = ttk.Progressbar(stat_bar, mode="indeterminate", length=200)
        self.progress_bar.pack(side=tk.RIGHT, padx=4)

        # 日志文本输出框
        log_header = ttk.Frame(bot_frame)
        log_header.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(log_header, text="执行日志控制台 (Execution Log):", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        ttk.Button(log_header, text="清空控制台", command=self._clear_logs).pack(side=tk.RIGHT)

        self.log_text = scrolledtext.ScrolledText(
            bot_frame,
            height=10,
            bg="#1E1E1E",
            fg="#D4D4D4",
            insertbackground="#FFFFFF",
            font=("Consolas", 9),
            wrap=tk.WORD
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

        # 配置彩色日志标签
        self.log_text.tag_config("INFO", foreground="#64B5F6")
        self.log_text.tag_config("PASS", foreground="#81C784")
        self.log_text.tag_config("FAIL", foreground="#E57373")
        self.log_text.tag_config("WARN", foreground="#FFD54F")

    def _poll_log_queue(self) -> None:
        """从队列中提取控制台输出并追加到文本框"""
        while not self.log_queue.empty():
            try:
                msg = self.log_queue.get_nowait()
                tag = None
                if "[PASS]" in msg or "PASSED" in msg or "100%" in msg:
                    tag = "PASS"
                elif "[FAIL]" in msg or "FAILED" in msg or "Error" in msg:
                    tag = "FAIL"
                elif "[WARN]" in msg:
                    tag = "WARN"

                if tag:
                    self.log_text.insert(tk.END, msg, tag)
                else:
                    self.log_text.insert(tk.END, msg)
                self.log_text.see(tk.END)
            except queue.Empty:
                break
        self.root.after(100, self._poll_log_queue)

    def _clear_logs(self) -> None:
        self.log_text.delete("1.0", tk.END)

    # =========================================================================
    # 文件与目录选择交互辅助方法
    # =========================================================================
    def _browse_dir(self, target_var: tk.StringVar) -> None:
        initial = target_var.get() if os.path.exists(target_var.get()) else self.default_workspace
        selected = filedialog.askdirectory(initialdir=initial, title="选择目录")
        if selected:
            target_var.set(os.path.normpath(selected))

    def _browse_file(self, target_var: tk.StringVar, filetypes: str = "*.csv") -> None:
        initial = os.path.dirname(target_var.get()) if target_var.get() else self.default_workspace
        selected = filedialog.askopenfilename(
            initialdir=initial,
            title="选择文件",
            filetypes=[("表格文件", filetypes), ("全部文件", "*.*")]
        )
        if selected:
            target_var.set(os.path.normpath(selected))

    def _browse_save_file(self, target_var: tk.StringVar, def_ext: str = "*.csv") -> None:
        initial = os.path.dirname(target_var.get()) if target_var.get() else self.default_workspace
        selected = filedialog.asksaveasfilename(
            initialdir=initial,
            title="保存文件至",
            filetypes=[("文件", def_ext), ("全部文件", "*.*")]
        )
        if selected:
            target_var.set(os.path.normpath(selected))

    def _open_dir(self, path: str) -> None:
        if os.path.exists(path):
            if os.path.isfile(path):
                path = os.path.dirname(path)
            subprocess.Popen(f'explorer "{os.path.normpath(path)}"')
        else:
            messagebox.showwarning("提示", f"目标路径不存在:\n{path}")

    def _open_dir_of_file(self, file_path: str) -> None:
        if file_path and os.path.exists(os.path.dirname(file_path)):
            subprocess.Popen(f'explorer "{os.path.normpath(os.path.dirname(file_path))}"')
        else:
            messagebox.showwarning("提示", "文件或目录尚未生成！")

    def _open_file(self, file_path: str) -> None:
        if os.path.exists(file_path):
            os.startfile(file_path)
        else:
            messagebox.showwarning("提示", f"报告文件尚未生成:\n{file_path}")

    def _open_doc(self, doc_filename: str) -> None:
        p = get_bundle_resource(doc_filename)
        if os.path.exists(p):
            try:
                os.startfile(p)
            except Exception:
                webbrowser.open(p)
        else:
            messagebox.showwarning("提示", f"文档未找到:\n{p}")

    def _open_web_console(self) -> None:
        def run_web():
            try:
                import plc_web_gui
                plc_web_gui.start_server(port=8989)
            except Exception as e:
                print(f"[Web Console] 启动异常: {e}")
        threading.Thread(target=run_web, daemon=True).start()
        webbrowser.open("http://127.0.0.1:8989")

    # =========================================================================
    # 异步任务调度器 (Background Worker Runner)
    # =========================================================================
    def _run_in_background(self, target_func: Any, on_success_msg: str) -> None:
        """统一后台任务启动器，接管 stdout/stderr 并展示进度条"""
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("运行中", "当前已有任务在执行中，请等待完成！")
            return

        self.progress_bar.start(10)
        self.lbl_status.config(text="执行中，请稍候...", style="Status.TLabel")

        redirector = StdoutRedirector(self.log_queue)
        old_stdout = sys.stdout
        old_stderr = sys.stderr

        def thread_target():
            sys.stdout = redirector
            sys.stderr = redirector
            try:
                target_func()
                self.root.after(0, lambda: self._on_task_finished(True, on_success_msg))
            except Exception as ex:
                self.log_queue.put(f"\n[ERROR] 运行时异常: {str(ex)}\n")
                self.root.after(0, lambda: self._on_task_finished(False, f"执行失败: {str(ex)}"))
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        self.worker_thread = threading.Thread(target=thread_target, daemon=True)
        self.worker_thread.start()

    def _on_task_finished(self, success: bool, msg: str) -> None:
        self.progress_bar.stop()
        if success:
            self.lbl_status.config(text=f"完成 - {msg}", style="Success.TLabel")
            messagebox.showinfo("成功", msg)
        else:
            self.lbl_status.config(text=f"失败 - {msg}", style="Error.TLabel")
            messagebox.showerror("错误", msg)

    # =========================================================================
    # 业务逻辑动作绑定
    # =========================================================================
    def _start_process_vars(self) -> None:
        src = self.var_src_var.get().strip()
        dst_en = self.var_en_var.get().strip()
        dst_cn = self.var_cn_var.get().strip() if self.var_cn_enable.get() else None
        dst_md = self.var_md_var.get().strip() if self.var_md_enable.get() else None
        mode = self.var_mode_var.get()
        plat = self._get_selected_platform()
        lang = self._get_selected_target_lang()

        if not src or not os.path.exists(src):
            messagebox.showerror("错误", f"源文件或目录不存在:\n{src}")
            return

        # 动态加载修边机专用插件
        if self.var_trimmer_plugin_enable.get() and os.path.exists(self.trimmer_plugin_path):
            self.kernel.load_plugins_from_file(self.trimmer_plugin_path)

        def task():
            proc = toolkit.VarTableProcessor(mode=mode, kernel=self.kernel)
            if os.path.isfile(src):
                print(f"\n[VarTableProcessor] 开始处理单文件: {src} (平台: {plat}, 语种: {lang})")
                records = proc.process_file(src, dst_en, dst_cn, platform=plat, target_lang=lang)
                print(f"[PASS] 单文件处理完成: 共 {len(records)} 行数据")
            else:
                proc.process_directory(
                    src_dir=src,
                    dst_en_dir=dst_en,
                    dst_cn_dir=dst_cn,
                    report_md_path=dst_md,
                    project_title="Corning Machine Delivery"
                )

        self._run_in_background(task, "变量表批量翻译与规范化完成！")

    def _start_process_io(self) -> None:
        src = self.io_src_var.get().strip()
        dst_en = self.io_dst_en_var.get().strip()
        dst_cn = self.io_dst_cn_var.get().strip() if self.io_dst_cn_enable.get() else None
        plat = self._get_selected_platform()
        lang = self._get_selected_target_lang()

        if not src or not os.path.exists(src):
            messagebox.showerror("错误", f"源 IO 表文件不存在:\n{src}")
            return
        if not dst_en:
            messagebox.showerror("错误", "请指定纯英文输出文件路径！")
            return

        def task():
            proc = toolkit.IOTableProcessor(kernel=self.kernel)
            print(f"\n[IOTableProcessor] 开始处理 IO 注释表: {src} (平台: {plat}, 语种: {lang})")
            records = proc.process_file(src, dst_en, dst_cn, platform=plat, target_lang=lang)
            print(f"[PASS] IO 注释表处理完成: 共 {len(records)} 行软元件映射记录")

        self._run_in_background(task, "IO 注释表转换完成！")

    def _start_verify(self) -> None:
        target_dir = self.ver_target_var.get().strip()
        src_dir = self.ver_src_var.get().strip()
        is_var = (self.ver_type_var.get() == "var")

        if not os.path.exists(target_dir):
            messagebox.showerror("错误", f"待检验目录不存在:\n{target_dir}")
            return

        def task():
            passed = toolkit.TableVerifier.verify_directory(
                src_dir=src_dir,
                target_dir=target_dir,
                mode="B",
                is_var_table=is_var,
                kernel=self.kernel
            )
            if not passed:
                raise RuntimeError("质量验收门禁检测到违例项，请查看上方日志！")

        self._run_in_background(task, "质量验收门禁 100% 全部通过！")

    def _start_turnkey(self) -> None:
        m_root = self.turnkey_dir_var.get().strip()
        if not os.path.exists(m_root):
            messagebox.showerror("错误", f"机台目录不存在:\n{m_root}")
            return

        # 动态加载修边机专有插件
        if "3-修边机" in m_root and os.path.exists(self.trimmer_plugin_path):
            self.kernel.load_plugins_from_file(self.trimmer_plugin_path)

        def task():
            # 自动推导机台子目录
            src_gvl_dir = os.path.join(m_root, "io注释_备份_原始留档", "变量表")
            dst_en_dir = os.path.join(m_root, "变量表")
            dst_cn_dir = os.path.join(m_root, "io注释_备份_规范中文版", "变量表")
            report_md = os.path.join(dst_en_dir, "变量表中英文对照表_Corning交付版.md")

            if not os.path.exists(src_gvl_dir):
                raise FileNotFoundError(f"未找到变量表原始留档目录: {src_gvl_dir}")

            print(f"\n=======================================================")
            print(f" 启动整机交钥匙交付流水线: {os.path.basename(m_root)}")
            print(f"=======================================================")

            # 1. 批量处理基准变量表 (排除 _new.csv)
            proc = toolkit.VarTableProcessor(mode="B", kernel=self.kernel)
            all_records = {}
            raw_files = [f for f in sorted(os.listdir(src_gvl_dir)) if f.endswith('.csv') and not f.endswith('_new.csv')]

            print(f"[1/3] 扫描到 {len(raw_files)} 个基准变量表，执行批量翻译...")
            for fname in raw_files:
                sp = os.path.join(src_gvl_dir, fname)
                ep = os.path.join(dst_en_dir, fname)
                cp = os.path.join(dst_cn_dir, fname)
                recs = proc.process_file(sp, ep, cp)
                all_records[fname] = recs
                print(f"  -> 完成: {fname:24s} | 数据行数: {len(recs):5d}")

            # 2. 导出单一中英对照总表
            print(f"\n[2/3] 正在生成单一中英对照总表 Markdown 报告...")
            proc.generate_markdown_report(all_records, report_md, project_title=f"{os.path.basename(m_root)} Corning Delivery")

            # 3. 执行严苛 5 重质量验收门禁
            print(f"\n[3/3] 启动全量质量验收门禁...")
            all_passed = True
            for fname in raw_files:
                sp = os.path.join(src_gvl_dir, fname)
                ep = os.path.join(dst_en_dir, fname)
                ok, errs = toolkit.TableVerifier.verify_file(sp, ep, mode="B", is_var_table=True, kernel=self.kernel)
                if ok:
                    print(f"  [PASS] {fname:24s} | 100% 验收通过")
                else:
                    all_passed = False
                    print(f"  [FAIL] {fname:24s} | 异常: {errs}")

            if not all_passed:
                raise RuntimeError("整机质量校验未完全通过，请核对日志！")
            print(f"\nFINAL RESULT: 整机 {len(raw_files)} 个变量表全部通过 100% 验收门禁！\n")

        self._run_in_background(task, f"{os.path.basename(m_root)} 整机交钥匙交付与验收完成！")


def launch_gui() -> None:
    """GUI 启动入口 (支持 Tkinter 桌面端与 Web 浏览器控制台自动容灾降级)"""
    try:
        root = tk.Tk()
        app = PLCToolkitGUI(root)
        # 强制置顶并激活窗口焦点，防止被 Windows 资源管理器或 IDE 遮挡
        try:
            root.lift()
            root.attributes('-topmost', True)
            root.after(150, lambda: root.attributes('-topmost', False))
            root.focus_force()
        except Exception:
            pass
        root.mainloop()
    except Exception as ex:
        print(f"[提示] 桌面窗口引擎启动遇到系统限制 ({str(ex)})，正在自动启动本地 Web 浏览器控制台...")
        import plc_web_gui
        plc_web_gui.start_server(port=8989)


if __name__ == "__main__":
    launch_gui()
