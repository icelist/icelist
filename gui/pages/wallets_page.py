"""
Wallets 页面 —— 私钥管理（加密存储）
支持：Solana、EVM（ETH/BSC 共用）
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFormLayout, QGroupBox, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QInputDialog,
)

from ..widgets.cards import Card
from ..theme import COLORS

from core.vault import Vault, VaultLockedError


class WalletsPage(QWidget):
    wallets_changed = Signal()

    def __init__(self, vault: Vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self._build_ui()
        self._refresh_table()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 24)
        root.setSpacing(14)

        title = QLabel("钱包管理")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "私钥通过主密码 AES 加密后本地存储（never 上传）。强烈建议使用专用的『狙击钱包』，不要使用主钱包。"
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        # 锁定状态提示
        self.lock_hint = QLabel()
        self.lock_hint.setWordWrap(True)
        root.addWidget(self.lock_hint)
        self._refresh_lock_hint()

        # 导入表单
        form_card = Card()
        form_lay = QVBoxLayout(form_card)
        form_lay.setContentsMargins(20, 18, 20, 18)
        form_lay.setSpacing(10)

        form_title = QLabel("导入钱包")
        form_title.setObjectName("cardTitle")
        form_lay.addWidget(form_title)

        row = QHBoxLayout()
        self.chain_combo = QLineEdit("solana")  # 简化为文本；可改 QComboBox
        self.chain_combo.setPlaceholderText("链：solana / ethereum / bsc")
        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("备注（如 sniper-01）")
        row.addWidget(self.chain_combo)
        row.addWidget(self.label_input)
        form_lay.addLayout(row)

        self.pk_input = QLineEdit()
        self.pk_input.setPlaceholderText("私钥：Solana base58 / EVM 0x 开头 64 hex")
        self.pk_input.setEchoMode(QLineEdit.Password)
        form_lay.addWidget(self.pk_input)

        # 显示/隐藏 + 导入按钮
        btn_row = QHBoxLayout()
        self.show_btn = QPushButton("👁  显示")
        self.show_btn.setCheckable(True)
        self.show_btn.toggled.connect(self._toggle_pk_visibility)
        btn_row.addWidget(self.show_btn)
        btn_row.addStretch()
        import_btn = QPushButton("导入")
        import_btn.setObjectName("primaryBtn")
        import_btn.clicked.connect(self._on_import)
        btn_row.addWidget(import_btn)
        form_lay.addLayout(btn_row)

        root.addWidget(form_card)

        # 已有钱包表格
        list_card = Card()
        list_lay = QVBoxLayout(list_card)
        list_lay.setContentsMargins(20, 18, 20, 18)
        list_title = QLabel("已保存的钱包")
        list_title.setObjectName("cardTitle")
        list_lay.addWidget(list_title)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["链", "备注", "地址预览", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        list_lay.addWidget(self.table)

        root.addWidget(list_card, 1)

    def _toggle_pk_visibility(self, checked: bool) -> None:
        self.pk_input.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        self.show_btn.setText("🙈  隐藏" if checked else "👁  显示")

    def _refresh_lock_hint(self) -> None:
        if self.vault.is_locked():
            self.lock_hint.setText(
                f"<span style='color:{COLORS['warn']};'>"
                f"⚠  保险箱已锁定。首次使用请在 API 页面设置主密码，或点击下方『解锁』。"
                f"</span>"
            )
        else:
            self.lock_hint.setText(
                f"<span style='color:{COLORS['success']};'>"
                f"✓  保险箱已解锁。"
                f"</span>"
            )

    def _on_import(self) -> None:
        if self.vault.is_locked():
            self._prompt_unlock()
            if self.vault.is_locked():
                return

        chain = self.chain_combo.text().strip().lower()
        label = self.label_input.text().strip() or "default"
        pk = self.pk_input.text().strip()

        if chain not in ("solana", "ethereum", "bsc"):
            QMessageBox.warning(self, "错误", "链必须是 solana / ethereum / bsc")
            return
        if not pk:
            QMessageBox.warning(self, "错误", "请输入私钥")
            return

        try:
            self.vault.add_wallet(chain, label, pk)
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))
            return

        self.pk_input.clear()
        self.label_input.clear()
        self._refresh_table()
        self.wallets_changed.emit()
        QMessageBox.information(self, "成功", f"已导入 {chain} 钱包: {label}")

    def _prompt_unlock(self) -> None:
        pwd, ok = QInputDialog.getText(
            self, "解锁保险箱", "请输入主密码：",
            QLineEdit.Password,
        )
        if not ok or not pwd:
            return
        try:
            self.vault.unlock(pwd)
            self._refresh_lock_hint()
            self._refresh_table()
        except Exception as e:
            QMessageBox.critical(self, "解锁失败", str(e))

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        if self.vault.is_locked():
            return
        for w in self.vault.list_wallets():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(w["chain"]))
            self.table.setItem(row, 1, QTableWidgetItem(w["label"]))
            self.table.setItem(row, 2, QTableWidgetItem(w.get("address_preview", "—")))
            del_btn = QPushButton("删除")
            del_btn.setObjectName("dangerBtn")
            del_btn.clicked.connect(lambda _, c=w["chain"], l=w["label"]:
                                    self._on_delete(c, l))
            self.table.setCellWidget(row, 3, del_btn)

    def _on_delete(self, chain: str, label: str) -> None:
        ret = QMessageBox.question(
            self, "确认删除", f"确定删除 {chain}/{label} 钱包？\n此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        self.vault.remove_wallet(chain, label)
        self._refresh_table()
        self.wallets_changed.emit()
