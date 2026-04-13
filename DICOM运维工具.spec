# -*- mode: python ; coding: utf-8 -*-

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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5', 'PySide6', 'PySide2', 'PyQt6',
        'sqlalchemy', 'pandas', 'IPython', 'jupyter',
        'matplotlib', 'scipy', 'sklearn', 'sqlite3',
        'pytest', 'unittest', 'urllib3', 'email', 'html', 'http', 'xml', 'xmlrpc',
        'pydoc_data', 'distutils', 'setuptools', 'pip', 'pkg_resources',
        'bz2', 'lzma', 'curses'
    ],
    noarchive=False,
    optimize=2,
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
    upx=True,
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
