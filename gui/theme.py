"""
深色主题 QSS + 配色常量
灵感：GitHub Dark + VS Code Dark+ + 自定义强调色
"""

# 配色调色板
COLORS = {
    "bg":          "#0d1117",   # 主背景
    "bg_panel":    "#161b22",   # 面板背景
    "bg_hover":    "#1f2937",   # hover 背景
    "bg_active":   "#1f6feb22", # 选中背景（半透明）
    "border":      "#30363d",
    "text":        "#c9d1d9",
    "text_mute":   "#8b949e",
    "text_bright": "#f0f6fc",
    "accent":      "#58a6ff",   # 主强调（Solana 粉紫）
    "accent2":     "#bd93f9",
    "success":     "#3fb950",
    "warn":        "#d29922",
    "error":       "#f85149",
    "solana":      "#bd93f9",
    "bsc":         "#f0b90b",
    "ethereum":    "#00d3f2",
}


QSS = f"""
/* ========== 全局 ========== */
* {{
    font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 13px;
    color: {COLORS['text']};
    outline: 0;
}}

QMainWindow, QWidget#centralWidget {{
    background-color: {COLORS['bg']};
}}

QToolTip {{
    background: {COLORS['bg_panel']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    padding: 4px 8px;
    border-radius: 4px;
}}

/* ========== Sidebar ========== */
QWidget#sidebar {{
    background-color: {COLORS['bg_panel']};
    border-right: 1px solid {COLORS['border']};
}}

QLabel#logo {{
    color: {COLORS['accent']};
    font-size: 18px;
    font-weight: 700;
    padding: 18px 20px 8px 20px;
    letter-spacing: 1px;
}}

QLabel#logoSub {{
    color: {COLORS['text_mute']};
    font-size: 10px;
    padding: 0 20px 18px 20px;
    letter-spacing: 2px;
}}

QPushButton#navBtn {{
    text-align: left;
    padding: 12px 20px;
    border: 0;
    border-left: 3px solid transparent;
    background: transparent;
    color: {COLORS['text_mute']};
    font-size: 14px;
}}

QPushButton#navBtn:hover {{
    background: {COLORS['bg_hover']};
    color: {COLORS['text_bright']};
}}

QPushButton#navBtn:checked {{
    background: {COLORS['bg_active']};
    border-left: 3px solid {COLORS['accent']};
    color: {COLORS['text_bright']};
    font-weight: 600;
}}

QPushButton#startBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #58a6ff, stop:1 #bd93f9);
    color: white;
    border: 0;
    border-radius: 8px;
    padding: 12px 20px;
    font-size: 14px;
    font-weight: 700;
}}

QPushButton#startBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #6eb3ff, stop:1 #cba7fc);
}}

QPushButton#startBtn:disabled {{
    background: {COLORS['bg_hover']};
    color: {COLORS['text_mute']};
}}

QPushButton#stopBtn {{
    background: {COLORS['error']};
    color: white;
    border: 0;
    border-radius: 8px;
    padding: 12px 20px;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton#stopBtn:hover {{ background: #ff6961; }}

/* ========== Card ========== */
QFrame#card {{
    background: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
}}

QFrame#card:hover {{
    border-color: {COLORS['accent']};
}}

QLabel#cardTitle {{
    font-size: 14px;
    font-weight: 700;
    color: {COLORS['text_bright']};
}}

QLabel#cardDesc {{
    color: {COLORS['text_mute']};
    font-size: 12px;
}}

QLabel#statValue {{
    font-size: 22px;
    font-weight: 700;
    color: {COLORS['text_bright']};
}}

QLabel#statLabel {{
    color: {COLORS['text_mute']};
    font-size: 11px;
    letter-spacing: 1px;
}}

QLabel#pnlPositive {{
    color: {COLORS['success']};
    font-size: 22px;
    font-weight: 700;
}}

QLabel#pnlNegative {{
    color: {COLORS['error']};
    font-size: 22px;
    font-weight: 700;
}}

/* ========== Input ========== */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {COLORS['bg']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 8px 10px;
    color: {COLORS['text']};
    selection-background-color: {COLORS['accent']};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {COLORS['accent']};
}}

QLineEdit:disabled {{
    color: {COLORS['text_mute']};
    background: {COLORS['bg_panel']};
}}

QComboBox::drop-down {{ border: 0; }}
QComboBox QAbstractItemView {{
    background: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['bg_hover']};
}}

/* ========== Button ========== */
QPushButton {{
    background: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 8px 16px;
    color: {COLORS['text']};
}}
QPushButton:hover {{
    background: {COLORS['bg_hover']};
    border-color: {COLORS['accent']};
}}
QPushButton:pressed {{ background: {COLORS['bg_active']}; }}
QPushButton:disabled {{ color: {COLORS['text_mute']}; }}

QPushButton#primaryBtn {{
    background: {COLORS['accent']};
    color: white;
    border: 0;
    font-weight: 600;
}}
QPushButton#primaryBtn:hover {{ background: #79b8ff; }}

QPushButton#dangerBtn {{
    background: transparent;
    color: {COLORS['error']};
    border: 1px solid {COLORS['error']};
}}
QPushButton#dangerBtn:hover {{
    background: {COLORS['error']};
    color: white;
}}

/* ========== Table ========== */
QTableWidget {{
    background: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    gridline-color: {COLORS['border']};
    alternate-background-color: {COLORS['bg']};
}}
QTableWidget::item {{
    padding: 6px;
    border: 0;
}}
QTableWidget::item:selected {{
    background: {COLORS['bg_active']};
    color: {COLORS['text_bright']};
}}
QHeaderView::section {{
    background: {COLORS['bg']};
    color: {COLORS['text_mute']};
    padding: 8px;
    border: 0;
    border-bottom: 1px solid {COLORS['border']};
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
}}

/* ========== ScrollBar ========== */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['border']};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {COLORS['text_mute']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{
    background: {COLORS['border']};
    border-radius: 5px;
    min-width: 30px;
}}

/* ========== Checkbox / Switch ========== */
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    background: {COLORS['bg']};
}}
QCheckBox::indicator:checked {{
    background: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}

/* ========== GroupBox ========== */
QGroupBox {{
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 16px;
    color: {COLORS['text_mute']};
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {COLORS['text_bright']};
}}

/* ========== Tabs ========== */
QTabWidget::pane {{
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {COLORS['text_mute']};
    padding: 8px 16px;
    border: 1px solid transparent;
}}
QTabBar::tab:selected {{
    color: {COLORS['text_bright']};
    border-bottom: 2px solid {COLORS['accent']};
}}

/* ========== TitleBar spacing ========== */
QLabel#pageTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {COLORS['text_bright']};
}}
QLabel#pageSubtitle {{
    color: {COLORS['text_mute']};
    font-size: 12px;
}}

/* ========== Status badges ========== */
QLabel#badgeRunning {{
    background: #238636;
    color: white;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 700;
}}
QLabel#badgeStopped {{
    background: {COLORS['bg_hover']};
    color: {COLORS['text_mute']};
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 700;
}}
"""


def chain_color(chain: str) -> str:
    return COLORS.get(chain, COLORS["accent"])
