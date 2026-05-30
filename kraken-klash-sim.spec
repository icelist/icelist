# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec —— Kraken Klash 单机模拟器
=========================================

用法:
    pyinstaller kraken-klash-sim.spec --clean --noconfirm

产物:
    dist/KrakenKlashSim.exe   (Windows)
    dist/KrakenKlashSim       (macOS/Linux)

注意:
    这个 exe 是**纯单机离线**版本：
    - 不依赖 PySide6 / Web3 / Solana 等重型依赖
    - 仅用 typer + rich + questionary + pyyaml
    - 体积约 15-25MB（远小于主仓的 ChainSniper 那 ~100MB）
"""
from pathlib import Path
import sys

ROOT = Path(SPECPATH)
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

block_cipher = None


# 模块打包清单 —— 只把 sim 用到的拉进来
PROJECT_MODULES = [
    'tools',
    'tools.kraken_klash_sim',
    'tools.kraken_klash_sim.engine',
    'tools.kraken_klash_sim.strategies',
    'tools.kraken_klash_sim.ev',
    'tools.kraken_klash_sim.simulate',
    'tools.kraken_klash_sim.play',
    'tools.kraken_klash_sim.cli',
]

THIRDPARTY_HIDDEN = [
    'typer',
    'click',                        # typer 依赖
    'rich', 'rich.console', 'rich.panel', 'rich.table', 'rich.text',
    'rich.align', 'rich.traceback',
    'questionary', 'prompt_toolkit',
    'yaml',
]

# 把示例配置打包进去，让 exe 不依赖外部文件就能跑
data_files = [
    ('tools/kraken_klash_sim/config.example.yaml', 'tools/kraken_klash_sim'),
    ('tools/kraken_klash_sim/README.md', 'tools/kraken_klash_sim'),
]


a = Analysis(
    ['kraken_klash_sim_launcher.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=data_files,
    hiddenimports=PROJECT_MODULES + THIRDPARTY_HIDDEN,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # 排除主仓库才用得上的重型依赖，瘦身
        'PySide6', 'PyQt5', 'PyQt6', 'PySide2', 'qtawesome',
        'web3', 'eth_account', 'eth_typing', 'eth_utils', 'hexbytes',
        'solana', 'solders', 'base58',
        'cryptography',
        'aiohttp', 'multidict', 'yarl', 'frozenlist',
        'loguru',
        'tkinter', 'matplotlib', 'notebook', 'IPython', 'pytest',
        'scipy', 'numpy', 'pandas',
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
    name='KrakenKlashSim',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,    # 这是 TUI 程序，必须保留控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
