# -*- mode: python ; coding: utf-8 -*-
import os

# ui/, utils/, conversion/ and pc_report/ are deliberately NOT listed in datas.
# They are real packages and PyInstaller already freezes them into the archive;
# listing them as data copied the source tree into the bundle a second time.
#
# help_document.pdf is included only when it exists. ui/main_window.py's
# open_help_document() prefers the PDF and falls back to help_document.html, so
# without this entry a frozen build could never use the PDF at all.
_optional_datas = [
    (name, '.') for name in ('help_document.pdf',) if os.path.exists(name)
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('ffmpeg.exe', '.'), ('ffprobe.exe', '.')],
    datas=[
        ('graphics', 'graphics'),
        ('help_document.html', '.'),
        ('Paradise.mp3', '.'),
    ] + _optional_datas,
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
