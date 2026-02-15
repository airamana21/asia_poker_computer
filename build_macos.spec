# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

a = Analysis(
    ['src/app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/gui/style.qss', 'src/gui'),
        ('assets/cards', 'assets/cards'),  # Optional: pre-bundle cards
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'multiprocessing',
        'multiprocessing.spawn',
        'src.core.cards',
        'src.core.ranks',
        'src.core.partition',
        'src.core.house_way',
        'src.core.simulate',
        'src.core.evaluator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AsiaPoker421',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AsiaPoker421',
)

app = BUNDLE(
    coll,
    name='AsiaPoker421.app',
    icon='assets/icon.icns' if os.path.exists('assets/icon.icns') else None,
    bundle_identifier='com.asiapoker.421',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'CFBundleShortVersionString': '1.0.0',
    },
)
