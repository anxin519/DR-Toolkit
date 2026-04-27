# -*- mode: python ; coding: utf-8 -*-
# Win7 32位 Python 3.8 专用打包配置
# 在 Win7 32位机器上执行：pyinstaller build_win7.spec

a = Analysis(
    ['src/main_complete.py'],
    pathex=['src'],
    binaries=[],
    datas=[('config', 'config')],
    hiddenimports=[
        'ttkbootstrap',
        'ttkbootstrap.themes',
        'ttkbootstrap.style',
        'pynetdicom',
        'pydicom',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.ImageDraw',
        'openpyxl',
        'numpy',
        'pkg_resources',
        'jaraco',
        'jaraco.text',
        'jaraco.functools',
        'jaraco.context',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'PySide6', 'PySide2', 'PyQt6',
        'sqlalchemy', 'pandas', 'IPython', 'jupyter',
        'matplotlib', 'scipy', 'sklearn',
        'pytest', 'unittest',
        'bz2', 'lzma', 'curses',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DICOM运维工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # Win7上UPX容易出问题，关闭
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)
