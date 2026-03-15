@echo off
REM 打包为Windows可执行文件
pip install pyinstaller
pyinstaller --onefile --windowed --name="DICOM运维工具" --icon=icon.ico src/main.py
echo 打包完成，可执行文件在 dist 目录
pause
