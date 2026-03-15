@echo off
chcp 65001 >nul
echo ========================================
echo   DICOM运维工具 v2.0
echo ========================================
echo.
echo 正在启动程序...
echo.

python src/main_complete.py

if errorlevel 1 (
    echo.
    echo 启动失败！请检查：
    echo 1. Python是否已安装
    echo 2. 依赖是否已安装: pip install -r requirements_full.txt
    echo.
    pause
)
