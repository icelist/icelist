# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec —— Windows / macOS / Linux 通用
用法: pyinstaller chain-sniper.spec --clean --noconfirm
"""
from pathlib import Path
import sys

ROOT = Path(SPECPATH)
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

block_cipher = None


# 项目内所有子模块都手动列出，避免 PyInstaller 静态分析漏掉
PROJECT_MODULES = [
    # core
    'core', 'core.base', 'core.config', 'core.logger', 'core.notifier',
    'core.vault', 'core.safety',
    # chains
    'chains', 'chains.solana', 'chains.solana.client',
    'chains.evm', 'chains.evm.client',
    # functions
    'functions', 'functions.solana_fns', 'functions.bsc_fns', 'functions.eth_fns',
    # gui
    'gui', 'gui.main_window', 'gui.theme', 'gui.log_bridge', 'gui.runner',
    'gui.pages', 'gui.pages.dashboard_page', 'gui.pages.functions_page',
    'gui.pages.wallets_page', 'gui.pages.api_page', 'gui.pages.logs_page',
    'gui.widgets', 'gui.widgets.cards',
    # ui（CLI 模式）
    'ui', 'ui.banner', 'ui.dashboard', 'ui.menu', 'ui.theme',
]


# 第三方库 hidden imports —— PySide6 / Web3 / Solana 都有大量动态 import
THIRDPARTY_HIDDEN = [
    # Qt
    'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
    'PySide6.QtNetwork', 'PySide6.QtSvg',
    # Solana
    'solana', 'solana.rpc.async_api', 'solana.rpc.types',
    'solders', 'solders.keypair', 'solders.pubkey', 'solders.signature',
    'solders.transaction',
    'base58',
    'websockets', 'websockets.client', 'websockets.asyncio.client',
    # EVM
    'web3', 'web3.providers.async_rpc', 'web3._utils.abi',
    'eth_account', 'eth_account.account',
    'eth_typing', 'eth_utils', 'hexbytes',
    # 加密
    'cryptography', 'cryptography.fernet',
    'cryptography.hazmat.primitives.kdf.pbkdf2',
    'cryptography.hazmat.primitives.hashes',
    'cryptography.hazmat.backends',
    # 其他
    'aiohttp', 'multidict', 'yarl', 'frozenlist',
    'loguru',
    'yaml', 'dotenv',
    'rich', 'rich.console', 'rich.panel', 'rich.table', 'rich.text',
    'questionary', 'prompt_toolkit',
    'pyfiglet',
    'typer',
    'pydantic', 'pydantic_core',
    'qtawesome',
]


data_files = [
    ('config.yaml', '.'),
]
# .env.example 存在才加入
if (ROOT / '.env.example').exists():
    data_files.append(('.env.example', '.'))


a = Analysis(
    ['app.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=data_files,
    hiddenimports=PROJECT_MODULES + THIRDPARTY_HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'notebook', 'IPython', 'pytest',
        'PyQt5', 'PyQt6', 'PySide2',  # 避免 Qt 冲突
        'scipy', 'numpy.testing', 'pandas',  # 不用的大包
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 图标处理
icon_file = None
if IS_WIN and (ROOT / 'assets' / 'icon.ico').exists():
    icon_file = str(ROOT / 'assets' / 'icon.ico')
elif IS_MAC and (ROOT / 'assets' / 'icon.icns').exists():
    icon_file = str(ROOT / 'assets' / 'icon.icns')


exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ChainSniper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,       # 启用 UPX 易被杀软误报，关闭
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,   # False = 纯 GUI；调试可改 True 看 Python 错误
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
        name='ChainSniper.app',
        icon=icon_file,
        bundle_identifier='com.chainsniper.app',
        info_plist={
            'CFBundleName': 'ChainSniper',
            'CFBundleDisplayName': 'Chain Sniper',
            'CFBundleShortVersionString': '0.1.0',
            'CFBundleVersion': '0.1.0',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.13.0',
        },
    )
