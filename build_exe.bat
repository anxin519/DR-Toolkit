@echo off
chcp 65001 >nul
echo 正在打包 DICOM 运维工具...

pip install pyinstaller >nul 2>&1

pyinstaller ^
  --onefile ^
  --windowed ^
  --name="DICOM运维工具" ^
  --add-data "config;config" ^
  --hidden-import ttkbootstrap ^
  --hidden-import pynetdicom ^
  --hidden-import pydicom ^
  --hidden-import PIL ^
  --hidden-import openpyxl ^
  --hidden-import numpy ^
  src/main_complete.py

echo.
echo 打包完成，可执行文件在 dist 目录
pause
