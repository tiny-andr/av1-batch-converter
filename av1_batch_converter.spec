# -*- mode: python ; coding: utf-8 -*-


# Run build.bat so the working directory is the spec directory.

import os

# Fail loudly rather than silently shipping an exe without ffmpeg inside it.
_FFMPEG = os.path.join(SPECPATH, 'vendor', 'ffmpeg', 'ffmpeg.exe')
if not os.path.isfile(_FFMPEG):
    raise SystemExit(
        'vendor/ffmpeg/ffmpeg.exe is missing. Run: '
        'python vendor/fetch_ffmpeg.py'
    )

a = Analysis(
    ['av1_batch_converter.pyw'],
    pathex=[],
    binaries=[],
    datas=[
        ('C:/Users/Administrator/.workbuddy/binaries/python/envs/av1_converter_sys/Lib/site-packages/tkinterdnd2/tkdnd', 'tkinterdnd2/tkdnd'),
        ('vendor/ffmpeg/ffmpeg.exe', 'ffmpeg'),
        ('vendor/ffmpeg/LICENSE', 'ffmpeg'),
        ('vendor/ffmpeg/README-ffmpeg.txt', 'ffmpeg'),
    ],
    hiddenimports=['tkinterdnd2', 'pywinstyles'],
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
    name='av1_batch_converter',
    version='version_info.txt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['ffmpeg.exe'],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
