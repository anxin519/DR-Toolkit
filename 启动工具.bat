@echo off
chcp 65001 >nul
echo 正在启动 DICOM 运维工具...
python src/main_complete.py
if %errorlevel% neq 0 (
    echo.
    echo 启动失败，请检查 Python 环境和依赖是否安装：
    echo   pip install -r requirements.txt
    pause
)
