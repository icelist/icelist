"""Qt 样式 / 配色."""
from __future__ import annotations

COLORS = {
    "bg":         "#0E1117",
    "panel":      "#161B22",
    "panel_alt":  "#1C232C",
    "border":     "#2A313C",
    "text":       "#E6EDF3",
    "text_mute":  "#8B949E",
    "primary":    "#3FB950",
    "primary_h":  "#46c95a",
    "danger":     "#F85149",
    "warn":       "#D29922",
    "accent":     "#58A6FF",
}

QSS = f"""
QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
    font-size: 13px;
}}

QFrame#panel, QGroupBox {{
    background: {COLORS['panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
}}
QGroupBox {{
    margin-top: 14px;
    padding: 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {COLORS['accent']};
}}

QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
    background: {COLORS['panel_alt']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 8px;
    color: {COLORS['text']};
    selection-background-color: {COLORS['accent']};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {COLORS['accent']};
}}

QPushButton {{
    background: {COLORS['panel_alt']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 7px 14px;
    color: {COLORS['text']};
}}
QPushButton:hover {{ background: #232b36; }}
QPushButton:pressed {{ background: #1a212b; }}
QPushButton:disabled {{ color: {COLORS['text_mute']}; }}

QPushButton#primary {{
    background: {COLORS['primary']};
    border: 1px solid {COLORS['primary']};
    color: #06140A;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: {COLORS['primary_h']}; }}

QPushButton#danger {{
    background: {COLORS['danger']};
    border: 1px solid {COLORS['danger']};
    color: #fff;
}}
QPushButton#danger:hover {{ background: #ff6b62; }}

QTabBar::tab {{
    background: {COLORS['panel_alt']};
    border: 1px solid {COLORS['border']};
    border-bottom: none;
    padding: 6px 14px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{
    background: {COLORS['primary']};
    color: #06140A;
    font-weight: 600;
}}
QTabWidget::pane {{
    border: 1px solid {COLORS['border']};
    border-radius: 0 6px 6px 6px;
    background: {COLORS['panel']};
}}

QTableWidget {{
    background: {COLORS['panel']};
    alternate-background-color: {COLORS['panel_alt']};
    gridline-color: {COLORS['border']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
}}
QHeaderView::section {{
    background: {COLORS['panel_alt']};
    color: {COLORS['text_mute']};
    border: none;
    border-right: 1px solid {COLORS['border']};
    border-bottom: 1px solid {COLORS['border']};
    padding: 6px;
    font-weight: 600;
}}
QTableWidget::item:selected {{
    background: rgba(63,185,80,0.18);
    color: {COLORS['text']};
}}

QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {COLORS['border']};
    border-radius: 3px;
    background: {COLORS['panel_alt']};
}}
QCheckBox::indicator:checked {{
    background: {COLORS['primary']};
    border: 1px solid {COLORS['primary']};
}}

QPlainTextEdit#log {{
    font-family: "Consolas", "Menlo", monospace;
    font-size: 12px;
    background: #0a0d12;
}}

QProgressBar {{
    background: {COLORS['panel_alt']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    text-align: center;
    color: {COLORS['text']};
}}
QProgressBar::chunk {{
    background: {COLORS['primary']};
    border-radius: 3px;
}}

QStatusBar {{ background: {COLORS['panel']}; color: {COLORS['text_mute']}; }}
"""
