@echo off
chcp 65001 >nul
echo 正在打包 DICOM 运维工具...

pip install pyinstaller >nul 2>&1

pyinstaller "DICOM运维工具.spec"

echo.
if exist "dist\DICOM运维工具.exe" (
    echo 打包成功！文件位于 dist\DICOM运维工具.exe
) else (
    echo 打包失败，请查看上方错误信息
)
pause
