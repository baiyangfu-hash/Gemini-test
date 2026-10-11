# -*- coding: utf-8 -*-
"""
=============================================================================
Corning PLC Table Toolkit - Standalone Windows 11 EXE 打包构建脚本
=============================================================================
执行：python build_exe.py
产物：
  dist/Corning_PLC_Toolkit_v2.0_Win64/
  ├── Corning_PLC_Toolkit.exe             <-- 单文件免安装主程序 (零外部依赖，直接双击运行)
  ├── README_工作流使用说明.md             <-- 完整操作手册
  ├── ARCHITECTURE_AND_EXTENSIBILITY.md   <-- 架构与接入白皮书
  └── plugins/                            <-- 外部插件目录
      ├── trimmer_dictionary_plugin.py
      └── demo_custom_plugin.py
"""

import os
import sys
import shutil
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_ROOT = os.path.dirname(CURRENT_DIR)
DIST_DIR = os.path.join(WORKFLOW_ROOT, "dist")
BUILD_DIR = os.path.join(WORKFLOW_ROOT, "build")
RELEASE_DIR = os.path.join(DIST_DIR, "Corning_PLC_Toolkit_v2.0_Win64")

def clean_previous() -> None:
    print("[1/5] 清理历史构建缓存...")
    for p in [BUILD_DIR, RELEASE_DIR]:
        if os.path.exists(p):
            shutil.rmtree(p, ignore_errors=True)
    for root_dir in [WORKFLOW_ROOT, CURRENT_DIR]:
        spec_path = os.path.join(root_dir, "Corning_PLC_Toolkit.spec")
        if os.path.exists(spec_path):
            try:
                os.remove(spec_path)
            except Exception:
                pass

def run_pyinstaller() -> None:
    print("[2/5] 启动 PyInstaller 生成独立可执行文件 (Windowed EXE)...")
    
    doc_readme = os.path.join(WORKFLOW_ROOT, "docs", "README_工作流使用说明.md")
    doc_arch = os.path.join(WORKFLOW_ROOT, "docs", "ARCHITECTURE_AND_EXTENSIBILITY.md")
    plugin_trimmer = os.path.join(WORKFLOW_ROOT, "plugins", "trimmer_dictionary_plugin.py")
    plugin_demo = os.path.join(WORKFLOW_ROOT, "plugins", "demo_custom_plugin.py")
    plugin_solar = os.path.join(WORKFLOW_ROOT, "plugins", "solar_frame_dictionary_plugin.py")
    entry_script = os.path.join(WORKFLOW_ROOT, "core", "plc_gui.py")

    add_data = [
        f"{doc_readme};.",
        f"{doc_arch};.",
        f"{plugin_trimmer};.",
        f"{plugin_demo};.",
        f"{plugin_solar};.",
    ]
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", "Corning_PLC_Toolkit",
        "--paths", os.path.join(WORKFLOW_ROOT, "core"),
        "--paths", os.path.join(WORKFLOW_ROOT, "plugins"),
        "--distpath", DIST_DIR,
        "--workpath", BUILD_DIR,
    ]
    
    for item in add_data:
        cmd.extend(["--add-data", item])
        
    cmd.extend([
        "--hidden-import", "plc_web_gui",
        "--hidden-import", "plc_table_toolkit",
        "--hidden-import", "table_inspector",
        "--hidden-import", "trimmer_dictionary_plugin",
        "--hidden-import", "demo_custom_plugin",
        "--hidden-import", "solar_frame_dictionary_plugin",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "tkinter.filedialog",
        "--hidden-import", "tkinter.messagebox",
        "--hidden-import", "tkinter.scrolledtext",
        "--hidden-import", "http.server",
        "--hidden-import", "urllib.parse",
        "--hidden-import", "webbrowser",
        entry_script
    ])
    
    print("执行命令:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=WORKFLOW_ROOT)
    if res.returncode != 0:
        raise RuntimeError(f"PyInstaller 构建失败，退出码: {res.returncode}")

def assemble_release_package() -> None:
    print("[3/5] 组装独立免安装分发包 (Release Package)...")
    os.makedirs(RELEASE_DIR, exist_ok=True)
    plugins_dir = os.path.join(RELEASE_DIR, "plugins")
    os.makedirs(plugins_dir, exist_ok=True)
    
    # 1. 移动/复制 exe
    src_exe = os.path.join(DIST_DIR, "Corning_PLC_Toolkit.exe")
    dst_exe = os.path.join(RELEASE_DIR, "Corning_PLC_Toolkit.exe")
    if os.path.exists(src_exe):
        shutil.copy2(src_exe, dst_exe)
    else:
        raise FileNotFoundError(f"未找到生成的 exe: {src_exe}")
        
    # 2. 复制说明文档
    docs = ["README_工作流使用说明.md", "ARCHITECTURE_AND_EXTENSIBILITY.md"]
    for d in docs:
        src = os.path.join(WORKFLOW_ROOT, "docs", d)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(RELEASE_DIR, d))
            
    # 3. 复制插件示例
    plugins = ["trimmer_dictionary_plugin.py", "demo_custom_plugin.py", "solar_frame_dictionary_plugin.py"]
    for p in plugins:
        src = os.path.join(WORKFLOW_ROOT, "plugins", p)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(plugins_dir, p))
            
    # 4. 生成备用浏览器快捷脚本
    web_bat = os.path.join(RELEASE_DIR, "以浏览器Web模式启动.bat")
    with open(web_bat, "w", encoding="utf-8") as f:
        f.write('@echo off\nchcp 65001 >nul\ncd /d "%~dp0"\necho 正在启动 Web 控制台...\nstart "" "Corning_PLC_Toolkit.exe"\nexit\n')

def verify_exe() -> None:
    print("[4/5] 校验生成产物完整性与文件大小...")
    dst_exe = os.path.join(RELEASE_DIR, "Corning_PLC_Toolkit.exe")
    if not os.path.exists(dst_exe):
        raise FileNotFoundError(f"校验失败: {dst_exe} 不存在")
    
    size_mb = os.path.getsize(dst_exe) / (1024 * 1024)
    print(f"  -> 生成 EXE 文件: {dst_exe}")
    print(f"  -> 文件大小: {size_mb:.2f} MB (已内嵌完整 Python 运行时、标准库及 Tkinter UI 引擎)")

def main() -> None:
    clean_previous()
    run_pyinstaller()
    assemble_release_package()
    verify_exe()
    print("\n[5/5] 打包成功！分发目录就绪:")
    print(f"  >> {RELEASE_DIR}\n")

if __name__ == "__main__":
    main()
