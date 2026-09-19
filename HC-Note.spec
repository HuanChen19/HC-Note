# -*- mode: python ; coding: utf-8 -*-
"""HC-Note PyInstaller 打包规格文件。

生成免安装单文件绿色版可执行程序，使用 --windowed 避免控制台黑框。
注意：assets 与 src/ui 必须以绝对路径加入 datas，否则相对路径会因
--specpath 的解析基准不同而导致资源缺失。
"""

import os

from PyInstaller.utils.hooks import collect_submodules


ROOT = os.path.abspath(os.path.dirname(SPEC))

datas = [
    (os.path.join(ROOT, "src", "ui"), "src/ui"),
    (os.path.join(ROOT, "assets"), "assets"),
]

hiddenimports = [
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "clr_loader",
    "pythonnet",
]

# 收集 pystray 各后端与 windows_toasts 子模块，避免被裁剪
hiddenimports += collect_submodules("pystray")
hiddenimports += collect_submodules("windows_toasts")

block_cipher = None

a = Analysis(
    [os.path.join(ROOT, "src", "backend", "app.py")],
    pathex=[os.path.join(ROOT, "src", "backend")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
    ],
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
    name="HC-Note",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "assets", "icons", "app.ico"),
)
