"""GUI 入口：双击 EXE 后启动这里."""
from __future__ import annotations

import sys
from pathlib import Path

# 确保 PyInstaller onefile 解压后能找到 scraper 包
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

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
