"""
GUI 入口 —— 双击 exe 或 python app.py 启动
"""
import sys
from pathlib import Path

# 确保打包后也能找到模块
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from gui.main_window import MainWindow
from gui.theme import QSS


def main() -> int:
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
    sys.exit(main())
