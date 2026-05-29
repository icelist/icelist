# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec —— Windows / macOS / Linux 通用
用法: pyinstaller product-scraper.spec --clean --noconfirm
"""
from pathlib import Path
import sys

ROOT = Path(SPECPATH)
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

block_cipher = None


# 项目内子模块（PyInstaller 静态分析有时漏掉）
PROJECT_MODULES = [
    "scraper",
    "scraper.base",
    "scraper.utils",
    "scraper.classifier",
    "scraper.storage",
    "scraper.alibaba1688",
    "scraper.pinduoduo",
    "gui",
    "gui.main_window",
    "gui.theme",
    "gui.scrape_worker",
]

# 第三方 hidden imports（DrissionPage / Qt 都有动态 import）
THIRDPARTY_HIDDEN = [
    # Qt
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    # DrissionPage
    "DrissionPage",
    "DrissionPage._configs",
    "DrissionPage._pages.chromium_page",
    "DrissionPage._pages.chromium_tab",
    "DrissionPage._units.actions",
    "websocket",
    "websocket._app",
    # 其他
    "yaml",
    "loguru",
    "tenacity",
    "tqdm",
    "openpyxl",
    "lxml",
    "lxml.etree",
    "PIL",
    "PIL.Image",
    "requests",
]


# 数据文件
data_files = []
if (ROOT / "config.yaml").exists():
    data_files.append(("config.yaml", "."))


a = Analysis(
    ["app.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=data_files,
    hiddenimports=PROJECT_MODULES + THIRDPARTY_HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "notebook",
        "IPython",
        "pytest",
        "PyQt5",
        "PyQt6",
        "PySide2",
        # 不再需要 pandas/numpy，显式排除以减小体积
        "pandas",
        "numpy",
        "scipy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 图标处理
icon_file = None
if IS_WIN and (ROOT / "assets" / "icon.ico").exists():
    icon_file = str(ROOT / "assets" / "icon.ico")
elif IS_MAC and (ROOT / "assets" / "icon.icns").exists():
    icon_file = str(ROOT / "assets" / "icon.icns")


exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ProductScraper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,         # 启用 UPX 易被杀软误报
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,     # 纯 GUI；调试时改 True 看 Python 错误
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)


# macOS 打成 .app bundle
if IS_MAC:
    app = BUNDLE(
        exe,
        name="ProductScraper.app",
        icon=icon_file,
        bundle_identifier="com.productscraper.app",
        info_plist={
            "CFBundleName": "ProductScraper",
            "CFBundleDisplayName": "Product Scraper",
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "0.1.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.13.0",
        },
    )
