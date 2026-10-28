# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all submodules for PySide6, OpenCV, PyZbar, and Argon2
hidden_imports = [
    'argon2',
    'cv2',
    'pyzbar',
    'pyzbar.pyzbar',
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'sqlite3',
]
hidden_imports += collect_submodules('src')

# Bundle static asset directories and database SQL schema
datas = [
    ('src/database/schema.sql', 'src/database'),
    ('src/ui/styles/theme.qss', 'src/ui/styles'),
]

if Path('assets').exists():
    datas.append(('assets', 'assets'))

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TGP_Attendance_System',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False to disable command prompt window on launch
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/images/logo.ico' if Path('assets/images/logo.ico').exists() else None,
)