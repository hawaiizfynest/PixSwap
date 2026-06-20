# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for PixSwap.

Builds a single-window GUI app:
  * Windows  -> dist/PixSwap/PixSwap.exe  (one-folder, then zipped by CI)
  * macOS    -> dist/PixSwap.app          (proper .app bundle)

tkinterdnd2 ships Tcl/Tk extension binaries as *data files* that PyInstaller
does not pick up automatically, so we collect them explicitly. pillow-heif's
codec libraries are pulled in the same way.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = []
binaries = []
hiddenimports = ["PIL._tkinter_finder"]

# tkinterdnd2: bundle its tkdnd platform binaries + python package data.
datas += collect_data_files("tkinterdnd2")

# pillow-heif: HEIC/HEIF codec shared libraries.
try:
    binaries += collect_dynamic_libs("pillow_heif")
    datas += collect_data_files("pillow_heif")
except Exception:
    pass

# Bundle icon files so the running window can set its titlebar/taskbar icon.
for _icon in ("icon.ico", "icon.png"):
    if os.path.exists(_icon):
        datas += [(_icon, ".")]

APP_NAME = "PixSwap"

# Auto-detect a custom icon if present (icon.ico on Windows, icon.icns on macOS).
if sys.platform == "darwin":
    ICON = "icon.icns" if os.path.exists("icon.icns") else None
elif sys.platform.startswith("win"):
    ICON = "icon.ico" if os.path.exists("icon.ico") else None
else:
    ICON = None

a = Analysis(
    ["photo_converter.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["numpy", "rawpy"],  # optional deps; excluded unless you add them
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # GUI app — no terminal window
    disable_windowed_traceback=False,
    argv_emulation=True,    # macOS: lets Finder "Open With" / drops pass file args
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

# On macOS, wrap the collected output into a proper .app bundle.
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=APP_NAME + ".app",
        icon=ICON,
        bundle_identifier="com.hawaiizfynest.pixswap",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleDisplayName": "PixSwap",
            "CFBundleName": "PixSwap",
        },
    )
