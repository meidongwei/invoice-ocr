# -*- mode: python ; coding: utf-8 -*-
"""Windows 打包配置：生成可双击的 发票识别.exe（目录版，更稳定）。"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

block_cipher = None
project_dir = Path(SPECPATH)

datas = []
binaries = []
paddlex_dir = project_dir / ".paddlex"
if paddlex_dir.exists():
    datas.append((str(paddlex_dir), ".paddlex"))

datas += collect_data_files(
    "paddlex",
    includes=[
        "configs/**/*.yaml",
        "configs/**/*.yml",
        "inference/**/*.yaml",
        "inference/**/*.yml",
        "inference/**/*.json",
        "utils/**/*.json",
    ],
)
datas += collect_data_files(
    "paddleocr",
    includes=[
        "**/*.yaml",
        "**/*.yml",
        "**/*.json",
        "**/*.txt",
    ],
)

# 收集 paddle / paddlex 的动态链接库 (.dll / .pyd)
for pkg in ("paddle", "paddleocr", "paddlex"):
    try:
        binaries += collect_dynamic_libs(pkg)
    except Exception:
        pass

# 尝试收集 paddle.libs 目录下的所有 DLL（paddlepaddle >= 3.x 可能用此目录）
import site
for root, dirs, files in os.walk(site.getsitepackages()[0]):
    root_name = os.path.basename(root)
    if root_name.endswith(".libs") and "paddle" in root_name.lower():
        for f in files:
            if f.endswith((".dll", ".pyd", ".so")):
                src = os.path.join(root, f)
                binaries.append((src, root_name))

hiddenimports = [
    "paddleocr",
    "paddle",
    "paddlex",
    "paddle._C_ops",
    "paddle.optimizer",
    "paddle.distributed",
    "pdfplumber",
    "pypdfium2",
    "PIL",
    "cv2",
    "numpy",
    "pandas",
    "shapely",
    "skimage",
    "yaml",
    "imgaug",
    "lanms",
    "lmdb",
    "pyclipper",
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "shiboken6",
]
hiddenimports += collect_submodules("paddleocr._pipelines")
hiddenimports += collect_submodules("paddleocr.pipelines")
hiddenimports += collect_submodules("paddlex.inference.pipelines")
hiddenimports += collect_submodules("paddlex.inference.models")
hiddenimports += collect_submodules("paddle")

a = Analysis(
    ["invoice_app.py"],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="发票识别",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    upx=False,
    upx_exclude=[],
    name="发票识别",
)
