"""
GUI 入口 —— 双击 exe 或 python app.py 启动

顶层 try/except 把启动错误写到 ~/.chain-sniper/crash.log，
即使日志系统本身崩溃也能留下诊断信息。
"""
import sys
import traceback
from pathlib import Path


def _write_crash(err: BaseException) -> Path:
    """写崩溃日志到用户目录，打包成 exe 时 stdout 为 None 也能看到"""
    crash_dir = Path.home() / ".chain-sniper"
    try:
        crash_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        import tempfile
        crash_dir = Path(tempfile.gettempdir()) / "chain-sniper"
        crash_dir.mkdir(parents=True, exist_ok=True)
    crash_file = crash_dir / "crash.log"
    try:
        with open(crash_file, "a", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            import datetime
            f.write(f"Crashed at: {datetime.datetime.now()}\n")
            f.write(f"Python: {sys.version}\n")
            f.write(f"Executable: {sys.executable}\n")
            f.write(f"Frozen: {getattr(sys, 'frozen', False)}\n")
            f.write("-" * 60 + "\n")
            traceback.print_exception(type(err), err, err.__traceback__, file=f)
            f.write("\n")
    except Exception:
        pass
    return crash_file


def _show_error_dialog(message: str, crash_file: Path) -> None:
    """错误对话框 —— 即使 QApplication 没起来也尝试"""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("Chain Sniper - Startup Error")
        box.setText("The program failed to start.")
        box.setInformativeText(
            f"Error log saved to:\n{crash_file}\n\n"
            f"Please send crash.log to the developer for debugging."
        )
        box.setDetailedText(message)
        box.exec()
    except Exception:
        # Qt 也起不来 —— 只能写日志
        pass


def main() -> int:
    # 延迟 import，保证 crash_log 路径可用
    ROOT = Path(__file__).resolve().parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon

    from gui.main_window import MainWindow
    from gui.theme import QSS

    app = QApplication(sys.argv)
    app.setApplicationName("Chain Sniper")
    app.setOrganizationName("chain-sniper")
    app.setStyleSheet(QSS)

    icon_path = ROOT / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    try:
        code = main()
        sys.exit(code if code is not None else 0)
    except (SystemExit, KeyboardInterrupt):
        # 正常退出，不当错误处理
        raise
    except Exception as e:
        tb = traceback.format_exc()
        crash_file = _write_crash(e)
        _show_error_dialog(tb, crash_file)
        sys.exit(1)
