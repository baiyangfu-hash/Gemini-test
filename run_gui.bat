@echo off
chcp 65001 >nul
title Corning PLC Table Toolkit GUI Launcher
cd /d "%~dp0"

echo =====================================================================
echo  Corning PLC 变量表与 IO 注释规范化套件 (GUI 桌面端)
echo =====================================================================
echo [1/3] 正在检测 Python 运行环境...

set "PYTHON_EXE=python"

:: 1. 尝试直接检测 python
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 goto :RUN

:: 2. 尝试 py 启动器
py --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_EXE=py"
    goto :RUN
)

:: 3. 尝试绝对路径
if exist "C:\Users\fubai\AppData\Local\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=C:\Users\fubai\AppData\Local\Programs\Python\Python311\python.exe"
    goto :RUN
)

echo [错误] 未能找到可用的 Python 运行环境！
echo 请确保 Python 已正确安装并配置到环境变量。
pause
exit /b 1

:RUN
echo [2/3] 使用 Python 路径: %PYTHON_EXE%
echo [3/3] 正在拉起图形界面，请稍候...
echo.

"%PYTHON_EXE%" core\plc_gui.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo =====================================================================
    echo [启动遇到异常] 程序退出码: %ERRORLEVEL%
    echo 如果窗口闪退，请查看上方的具体 Python 报错信息。
    echo =====================================================================
    pause
)
