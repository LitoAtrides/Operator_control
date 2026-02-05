# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

qt_webengine = collect_all('PySide6.QtWebEngineWidgets')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=qt_webengine['binaries'],
    datas=qt_webengine['datas'],
    hiddenimports=qt_webengine['hiddenimports'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EQueueBrowser',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
