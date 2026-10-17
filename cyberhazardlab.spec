# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

datas = [
    ('application/static', 'application/static'),
    ('application/soc', 'application/soc'),
    ('simulation_state.json', '.'),
]

hiddenimports = [
    'backend',
    'backend.orchestrator',
    'backend.core',
    'backend.core.node',
    'backend.core.host',
    'backend.network',
    'backend.network.network',
    'backend.services',
    'backend.services.dns',
    'backend.services.http',
    'backend.services.siem_agent',
    'backend.services.soc_engine',
    'backend.services.incident_pdf',
    'backend.state',
    'backend.state.manager',
    'backend.database',
    'backend.database.fs',
    'application',
    'application.api',
    'application.dns_resolver',
    'application.term_coms',
    'application.ncm',
    'application.ncm.ncm',
    'application.ntm',
    'application.ntm.ntm',
    'yaml',
]

a = Analysis(
    ['application/main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'numpy', 'test', 'unittest'],
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
    name='CyberHazardLab',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
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
    name='CyberHazardLab',
)
