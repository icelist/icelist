"""
深色主题 QSS —— 专业 sniper terminal 风格
参考 BullX / Photon / Axiom 的视觉语言
"""

# 配色调色板 - 更深、更饱和的交易终端色
COLORS = {
    "bg":          "#0a0e14",   # 主背景（比 GitHub 更深）
    "bg_panel":    "#12171f",   # 面板背景
    "bg_elev":     "#1a212c",   # 突出面板
    "bg_hover":    "#232b38",   # hover
    "bg_active":   "#2a3d5f",   # 选中
    "border":      "#2a3441",
    "border_hl":   "#3d4a5c",

    "text":        "#c5cdd9",
    "text_mute":   "#6e7a8f",
    "text_bright": "#f7fafc",
    "text_dim":    "#4a5464",

    "accent":      "#4c9aff",   # 主强调蓝
    "accent2":     "#b69aff",   # 紫
    "success":     "#00d48a",   # 绿 - 涨/买
    "success_dim": "#00a36b",
    "danger":      "#ff5757",   # 红 - 跌/卖
    "danger_dim":  "#d93838",
    "warn":        "#ffaa33",
    "info":        "#4c9aff",

    # 链品牌色
    "solana":      "#9945ff",
    "bsc":         "#f0b90b",
    "ethereum":    "#627eea",

    # 交易特殊
    "buy":         "#00d48a",
    "sell":        "#ff5757",
    "neutral":     "#4c9aff",
}


QSS = f"""
/* ========== 全局 ========== */
* {{
    font-family: "SF Pro Display", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 13px;
    color: {COLORS['text']};
    outline: 0;
}}

QMainWindow, QDialog, QWidget#centralWidget {{
    background-color: {COLORS['bg']};
}}

QToolTip {{
    background: {COLORS['bg_elev']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_hl']};
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 12px;
}}

/* ========== Sidebar ========== */
QWidget#sidebar {{
    background-color: {COLORS['bg_panel']};
    border-right: 1px solid {COLORS['border']};
}}

QLabel#logo {{
    color: {COLORS['accent']};
    font-size: 16px;
    font-weight: 800;
    padding: 20px 20px 4px 20px;
    letter-spacing: 2px;
}}

QLabel#logoSub {{
    color: {COLORS['text_mute']};
    font-size: 10px;
    padding: 0 20px 18px 20px;
    letter-spacing: 3px;
}}

QPushButton#navBtn {{
    text-align: left;
    padding: 11px 22px;
    border: 0;
    border-left: 3px solid transparent;
    background: transparent;
    color: {COLORS['text_mute']};
    font-size: 13px;
    font-weight: 500;
}}

QPushButton#navBtn:hover {{
    background: {COLORS['bg_hover']};
    color: {COLORS['text_bright']};
}}

QPushButton#navBtn:checked {{
    background: {COLORS['bg_active']};
    border-left: 3px solid {COLORS['accent']};
    color: {COLORS['text_bright']};
    font-weight: 700;
}}

/* ========== Card ========== */
QFrame#card {{
    background: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
}}

QFrame#card:hover {{
    border-color: {COLORS['border_hl']};
}}

QFrame#tokenCard {{
    background: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
}}
QFrame#tokenCard:hover {{
    border-color: {COLORS['accent']};
    background: {COLORS['bg_elev']};
}}

QFrame#widgetCard {{
    background: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
}}

QLabel#cardTitle {{
    font-size: 14px;
    font-weight: 700;
    color: {COLORS['text_bright']};
}}

QLabel#cardSubtitle {{
    font-size: 11px;
    color: {COLORS['text_mute']};
    letter-spacing: 1px;
    text-transform: uppercase;
}}

QLabel#cardDesc {{
    color: {COLORS['text_mute']};
    font-size: 12px;
}}

QLabel#statValue {{
    font-size: 24px;
    font-weight: 700;
    color: {COLORS['text_bright']};
}}

QLabel#statValueBig {{
    font-size: 28px;
    font-weight: 800;
    color: {COLORS['text_bright']};
}}

QLabel#statLabel {{
    color: {COLORS['text_mute']};
    font-size: 11px;
    letter-spacing: 1.5px;
    font-weight: 600;
    text-transform: uppercase;
}}

QLabel#pnlPositive {{
    color: {COLORS['success']};
    font-weight: 700;
}}

QLabel#pnlNegative {{
    color: {COLORS['danger']};
    font-weight: 700;
}}

/* ========== Token symbol / price ========== */
QLabel#tokenSymbol {{
    font-size: 16px;
    font-weight: 800;
    color: {COLORS['text_bright']};
    letter-spacing: 0.5px;
}}

QLabel#tokenAddr {{
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
    color: {COLORS['text_mute']};
}}

QLabel#tokenPrice {{
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 14px;
    font-weight: 700;
    color: {COLORS['text_bright']};
}}

QLabel#metricValue {{
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 13px;
    font-weight: 600;
    color: {COLORS['text_bright']};
}}

QLabel#metricLabel {{
    font-size: 10px;
    color: {COLORS['text_mute']};
    text-transform: uppercase;
    letter-spacing: 1px;
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

QLineEdit#amountInput {{
    background: {COLORS['bg']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 8px;
    font-family: "Cascadia Mono", monospace;
    font-weight: 700;
    font-size: 13px;
    color: {COLORS['text_bright']};
}}
QLineEdit#amountInput:focus {{
    border: 1px solid {COLORS['accent']};
    background: {COLORS['bg_panel']};
}}

QComboBox::drop-down {{ border: 0; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['bg_hover']};
    padding: 4px;
}}

/* ========== Button ========== */
QPushButton {{
    background: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 7px 14px;
    color: {COLORS['text']};
    font-weight: 500;
}}
QPushButton:hover {{
    background: {COLORS['bg_hover']};
    border-color: {COLORS['border_hl']};
}}
QPushButton:pressed {{ background: {COLORS['bg_active']}; }}
QPushButton:disabled {{ color: {COLORS['text_dim']}; border-color: {COLORS['border']}; }}

QPushButton#primaryBtn {{
    background: {COLORS['accent']};
    color: white;
    border: 0;
    font-weight: 700;
    padding: 9px 18px;
}}
QPushButton#primaryBtn:hover {{ background: #5ba8ff; }}

QPushButton#dangerBtn {{
    background: transparent;
    color: {COLORS['danger']};
    border: 1px solid {COLORS['danger']};
}}
QPushButton#dangerBtn:hover {{
    background: {COLORS['danger']};
    color: white;
}}

/* Buy / Sell 专属按钮 */
QPushButton#buyBtn {{
    background: {COLORS['buy']};
    color: #0a0e14;
    border: 0;
    border-radius: 6px;
    padding: 7px 12px;
    font-weight: 800;
    font-size: 12px;
    letter-spacing: 0.5px;
}}
QPushButton#buyBtn:hover {{ background: #1ae89c; }}
QPushButton#buyBtn:pressed {{ background: {COLORS['success_dim']}; }}
QPushButton#buyBtn:disabled {{ background: {COLORS['bg_hover']}; color: {COLORS['text_dim']}; }}

QPushButton#sellBtn {{
    background: {COLORS['sell']};
    color: white;
    border: 0;
    border-radius: 6px;
    padding: 7px 12px;
    font-weight: 800;
    font-size: 12px;
    letter-spacing: 0.5px;
}}
QPushButton#sellBtn:hover {{ background: #ff7070; }}
QPushButton#sellBtn:pressed {{ background: {COLORS['danger_dim']}; }}

/* 快速金额按钮 (0.1 / 0.5 / 1 SOL) */
QPushButton#quickAmt {{
    background: {COLORS['bg_elev']};
    border: 1px solid {COLORS['border']};
    border-radius: 5px;
    padding: 5px 10px;
    font-family: "Cascadia Mono", monospace;
    font-size: 11px;
    font-weight: 700;
    color: {COLORS['text']};
    min-width: 48px;
}}
QPushButton#quickAmt:hover {{
    background: {COLORS['accent']};
    color: white;
    border-color: {COLORS['accent']};
}}
QPushButton#quickAmt:checked {{
    background: {COLORS['accent']};
    color: white;
    border-color: {COLORS['accent']};
}}

/* Start / Stop large */
QPushButton#startBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {COLORS['accent']}, stop:1 {COLORS['accent2']});
    color: white;
    border: 0;
    border-radius: 8px;
    padding: 11px 20px;
    font-size: 13px;
    font-weight: 700;
}}
QPushButton#startBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #5ba8ff, stop:1 #c4acff);
}}
QPushButton#startBtn:disabled {{
    background: {COLORS['bg_hover']};
    color: {COLORS['text_mute']};
}}

QPushButton#stopBtn {{
    background: {COLORS['danger']};
    color: white;
    border: 0;
    border-radius: 8px;
    padding: 11px 20px;
    font-size: 13px;
    font-weight: 700;
}}
QPushButton#stopBtn:hover {{ background: #ff7070; }}

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
    font-weight: 700;
    font-size: 10px;
    letter-spacing: 1.2px;
}}

/* ========== ScrollBar ========== */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['border_hl']};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {COLORS['text_mute']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{
    background: {COLORS['border_hl']};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ========== Checkbox ========== */
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {COLORS['border_hl']};
    border-radius: 3px;
    background: {COLORS['bg']};
}}
QCheckBox::indicator:checked {{
    background: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}

/* ========== Tabs ========== */
QTabWidget::pane {{
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    top: -1px;
    background: {COLORS['bg_panel']};
}}
QTabBar::tab {{
    background: transparent;
    color: {COLORS['text_mute']};
    padding: 8px 18px;
    border: 1px solid transparent;
    font-weight: 600;
    font-size: 12px;
}}
QTabBar::tab:selected {{
    color: {COLORS['text_bright']};
    border-bottom: 2px solid {COLORS['accent']};
}}
QTabBar::tab:hover {{
    color: {COLORS['text']};
}}

/* ========== Splitter ========== */
QSplitter::handle {{
    background: {COLORS['bg']};
}}
QSplitter::handle:hover {{
    background: {COLORS['accent']};
}}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}

/* ========== Titles ========== */
QLabel#pageTitle {{
    font-size: 22px;
    font-weight: 800;
    color: {COLORS['text_bright']};
    letter-spacing: 0.3px;
}}
QLabel#pageSubtitle {{
    color: {COLORS['text_mute']};
    font-size: 12px;
}}

/* ========== Status badges ========== */
QLabel#badgeRunning {{
    background: {COLORS['success']};
    color: #0a0e14;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1px;
}}
QLabel#badgeStopped {{
    background: {COLORS['bg_hover']};
    color: {COLORS['text_mute']};
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#badgeNew {{
    background: {COLORS['accent']};
    color: white;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 800;
}}
QLabel#badgeHot {{
    background: {COLORS['warn']};
    color: #0a0e14;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 800;
}}
QLabel#badgeSafe {{
    background: {COLORS['success']};
    color: #0a0e14;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 10px;
    font-weight: 700;
}}
QLabel#badgeWarn {{
    background: {COLORS['warn']};
    color: #0a0e14;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 10px;
    font-weight: 700;
}}
QLabel#badgeDanger {{
    background: {COLORS['danger']};
    color: white;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 10px;
    font-weight: 700;
}}
"""


def chain_color(chain: str) -> str:
    return COLORS.get(chain, COLORS["accent"])
