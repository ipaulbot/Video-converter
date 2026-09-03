# -*- mode: python ; coding: utf-8 -*-
import os

# ui/, utils/, conversion/ and pc_report/ are deliberately NOT listed in datas.
# They are real packages and PyInstaller already freezes them into the archive;
# listing them as data copied the source tree into the bundle a second time.
#
# The generated manuals from docs/help are the primary help documents; see
# utils/help_resolution.py for the lookup. They are shipped into a docs/help
# subfolder so the same relative layout works frozen and from source.
import glob

_optional_datas = [(p, 'docs/help') for p in glob.glob('docs/help/NVC *.pdf')]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('ffmpeg.exe', '.'), ('ffprobe.exe', '.')],
    datas=[
        ('graphics', 'graphics'),
        ('Paradise.mp3', '.'),
    ] + _optional_datas,
    # ui.extras holds the easter-egg game (~2,200 lines). To ship without it,
    # add 'ui.extras' to excludes and drop Paradise.mp3 from datas.
    hiddenimports=['PyQt5.QtMultimedia'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='NVC',
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
    icon=['graphics\\NVCIcon.ico'],
)
