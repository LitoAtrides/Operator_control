# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

root = Path(SPECPATH)
# Standard PyInstaller Qt hooks collect WebEngineProcess, DLLs, locales and PAKs.
datas = [(str(root / 'config.json'), '.'),
         (str(root / 'assets/mapsoft_icon.ico'), 'assets'),
         (str(root / 'THIRD_PARTY_NOTICES.md'), '.')]
if (root / '.build-licenses').exists():
    datas.append((str(root / '.build-licenses'), 'third_party_licenses'))

a = Analysis(
    [str(root / 'main.py')],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='EQueueBrowser',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / 'assets/mapsoft_icon.ico'),
)
