"""GUI 入口：双击 EXE 后启动这里。

终版加固：
- 全局异常 hook：任何漏掉的异常都弹窗提示，绝不静默崩溃
- LogBridge 在最早期初始化
- _MEIPASS 路径处理
- 在 EXE 同目录建立工作目录，避免 cwd 被改变后找不到 .browser_profile / output
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

# ---------- PyInstaller 路径处理 ----------
def _exe_dir() -> Path:
    """获取 EXE 所在目录（onefile 模式下不是 _MEIPASS，是 EXE 本身位置）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


# 把 cwd 设到 EXE 所在目录，确保 .browser_profile 和 output 都在那里生成
try:
    os.chdir(_exe_dir())
except Exception:
    pass

# 让 PyInstaller 解压目录在 sys.path 里（onefile 用）
ROOT = Path(getattr(sys, "_MEIPASS", _exe_dir()))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------- 全局异常 hook ----------
def _excepthook(exc_type, exc_value, exc_tb):
    """任何未捕获异常 → 写日志 + 弹窗，不让 EXE 静默崩溃。"""
    try:
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    except Exception:
        msg = f"{exc_type.__name__}: {exc_value}"
    # 写到崩溃日志文件
    try:
        log_path = _exe_dir() / "crash.log"
        with log_path.open("a", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write(msg + "\n")
    except Exception:
        pass
    # 弹窗（只有在 QApplication 已存在时）
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        if QApplication.instance() is not None:
            QMessageBox.critical(None, "未预期的错误",
                f"程序遇到未处理的异常：\n\n{exc_type.__name__}: {exc_value}\n\n"
                f"已记录到 crash.log。请把该文件发给开发者。")
    except Exception:
        pass


sys.excepthook = _excepthook


# ---------- 早期初始化日志桥 ----------
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.log_bridge import LogBridge  # noqa: E402
LogBridge.instance()

from gui.main_window import MainWindow  # noqa: E402
from gui.theme import QSS  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("ProductScraper")
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
