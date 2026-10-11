@echo off
chcp 65001 >nul
title 汇川 PLC 变量表与 IO 注释标准化翻译工作流 (微内核套件)

echo =====================================================================
echo      Corning PLC 变量表与 IO 注释规范化与翻译工具 (工业微内核版)
echo =====================================================================
echo.

cd /d "%~dp0"

set "PYTHON_EXE=python"
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 goto :RUN
py --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_EXE=py"
    goto :RUN
)
if exist "C:\Users\fubai\AppData\Local\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=C:\Users\fubai\AppData\Local\Programs\Python\Python311\python.exe"
    goto :RUN
)

echo [错误] 未能找到 Python 运行环境！
pause
exit /b 1

:RUN
echo [1/2] 正在运行 3-修边机 全量基准变量表交付流水线...
"%PYTHON_EXE%" scripts\deliver_machine_3.py

echo.
echo =====================================================================
echo 处理完毕！按任意键退出...
echo =====================================================================
pause >nul
