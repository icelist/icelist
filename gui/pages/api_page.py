"""
API 设置页 —— RPC、WebSocket、Helius/Alchemy Key、Telegram Bot、通知
所有敏感 key 存在加密保险箱里；UI 以 Password 模式回显
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFormLayout, QMessageBox, QScrollArea, QInputDialog,
)

from ..widgets.cards import Card
from ..theme import COLORS

from core.vault import Vault


# 所有需要配置的 key —— 按分组
API_GROUPS = [
    ("Solana", [
        ("SOL_RPC_URL",  "RPC URL",           "https://api.mainnet-beta.solana.com", False),
        ("SOL_WS_URL",   "WebSocket URL",     "wss://api.mainnet-beta.solana.com",   False),
        ("HELIUS_KEY",   "Helius API Key",    "",                                     True),
        ("JITO_URL",     "Jito Block Engine", "https://mainnet.block-engine.jito.wtf", False),
    ]),
    ("Ethereum", [
        ("ETH_RPC_URL",  "RPC URL",           "https://eth.llamarpc.com", False),
        ("ETH_WS_URL",   "WebSocket URL",     "",                          False),
        ("ALCHEMY_ETH_KEY", "Alchemy Key",    "",                          True),
    ]),
    ("BNB Chain", [
        ("BSC_RPC_URL",  "RPC URL",           "https://bsc-dataseed.binance.org", False),
        ("BSC_WS_URL",   "WebSocket URL",     "",                                  False),
        ("QUICKNODE_BSC_KEY", "QuickNode Key", "",                                 True),
    ]),
    ("通知", [
        ("TELEGRAM_BOT_TOKEN", "Telegram Bot Token", "", True),
        ("TELEGRAM_CHAT_ID",   "Telegram Chat ID",    "", False),
        ("DISCORD_WEBHOOK_URL", "Discord Webhook",    "", True),
    ]),
    ("风险检测", [
        ("GOPLUS_KEY",      "GoPlus Security Key", "", True),
        ("RUGCHECK_KEY",    "Rugcheck Key",         "", True),
    ]),
]


class ApiPage(QWidget):
    api_saved = Signal()

    def __init__(self, vault: Vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self._inputs: dict[str, QLineEdit] = {}
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(12)

        title = QLabel("API / RPC 设置")
        title.setObjectName("pageTitle")
        subtitle = QLabel("所有敏感 API Key 通过主密码加密后本地存储。留空则使用默认公共节点（速度慢，不建议实盘）。")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        # 顶部工具：主密码按钮
        tool_row = QHBoxLayout()
        tool_row.addStretch()
        self.pwd_btn = QPushButton("🔐  设置 / 修改主密码")
        self.pwd_btn.clicked.connect(self._on_change_password)
        tool_row.addWidget(self.pwd_btn)
        save_btn = QPushButton("💾  保存全部")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._on_save)
        tool_row.addWidget(save_btn)
        root.addLayout(tool_row)

        # 滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setSpacing(12)

        for group_name, items in API_GROUPS:
            card = Card()
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(20, 16, 20, 16)
            card_lay.setSpacing(10)

            group_title = QLabel(group_name)
            group_title.setObjectName("cardTitle")
            card_lay.addWidget(group_title)

            form = QFormLayout()
            form.setContentsMargins(0, 6, 0, 0)
            form.setSpacing(8)
            for key, label, placeholder, is_secret in items:
                edit = QLineEdit()
                edit.setPlaceholderText(placeholder)
                if is_secret:
                    edit.setEchoMode(QLineEdit.Password)
                self._inputs[key] = edit
                form.addRow(f"{label}:", edit)
            card_lay.addLayout(form)
            inner_lay.addWidget(card)

        inner_lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

    def _load_values(self) -> None:
        if self.vault.is_locked():
            return
        vals = self.vault.get_api()
        for k, edit in self._inputs.items():
            edit.setText(vals.get(k, ""))

    def refresh(self) -> None:
        """保险箱解锁后调用"""
        self._load_values()

    def _ensure_vault_ready(self) -> bool:
        if not self.vault.is_initialized():
            pwd, ok = QInputDialog.getText(
                self, "设置主密码", "首次使用，请设置主密码（用于加密私钥和 API Key）：",
                QLineEdit.Password,
            )
            if not ok or not pwd:
                return False
            if len(pwd) < 6:
                QMessageBox.warning(self, "密码太短", "密码至少需要 6 位")
                return False
            confirm, ok2 = QInputDialog.getText(
                self, "确认密码", "再次输入以确认：",
                QLineEdit.Password,
            )
            if not ok2 or confirm != pwd:
                QMessageBox.warning(self, "不一致", "两次输入不一致")
                return False
            self.vault.init(pwd)
            return True

        if self.vault.is_locked():
            pwd, ok = QInputDialog.getText(
                self, "解锁保险箱", "请输入主密码：",
                QLineEdit.Password,
            )
            if not ok or not pwd:
                return False
            try:
                self.vault.unlock(pwd)
                return True
            except Exception as e:
                QMessageBox.critical(self, "错误", str(e))
                return False
        return True

    def _on_save(self) -> None:
        if not self._ensure_vault_ready():
            return
        data = {k: e.text().strip() for k, e in self._inputs.items() if e.text().strip()}
        self.vault.set_api(data)
        QMessageBox.information(self, "成功", f"已保存 {len(data)} 项配置")
        self.api_saved.emit()

    def _on_change_password(self) -> None:
        if not self.vault.is_initialized():
            self._ensure_vault_ready()
            return
        old, ok = QInputDialog.getText(self, "当前密码", "输入旧密码：", QLineEdit.Password)
        if not ok:
            return
        new, ok = QInputDialog.getText(self, "新密码", "输入新密码：", QLineEdit.Password)
        if not ok or len(new) < 6:
            QMessageBox.warning(self, "密码太短", "至少 6 位")
            return
        confirm, ok = QInputDialog.getText(self, "确认", "再次输入：", QLineEdit.Password)
        if not ok or confirm != new:
            QMessageBox.warning(self, "不一致", "两次输入不一致")
            return
        try:
            self.vault.change_password(old, new)
            QMessageBox.information(self, "成功", "密码已更新")
        except Exception as e:
            QMessageBox.critical(self, "失败", str(e))
