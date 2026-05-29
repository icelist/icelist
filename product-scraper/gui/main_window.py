"""主窗口：顶部参数 + 中间分类Tab+商品表 + 底部一键操作 + 日志."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import yaml
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from scraper.base import Product
from scraper.classifier import classify_products
from scraper.storage import Storage

from .log_bridge import LogBridge
from .scrape_worker import ScrapeWorker


# ----------- 默认配置（也会尝试从 config.yaml 读取） -----------
DEFAULT_CFG: dict = {
    "platforms": ["alibaba1688", "pinduoduo"],
    "keywords": ["蓝牙耳机", "保温杯"],
    "urls": [],
    "per_keyword_limit": 30,
    "max_pages": 2,
    "download_images": True,
    "price_buckets": [
        {"name": "0-50", "min": 0, "max": 50},
        {"name": "50-200", "min": 50, "max": 200},
        {"name": "200-500", "min": 200, "max": 500},
        {"name": "500-2000", "min": 500, "max": 2000},
        {"name": "2000+", "min": 2000, "max": 999999999},
    ],
    "type_rules": {
        "数码电器": ["耳机", "音箱", "充电宝", "数据线", "充电器", "手机", "电脑", "平板"],
        "家居日用": ["保温杯", "水杯", "毛巾", "牙刷", "收纳", "拖鞋", "枕头"],
        "服饰鞋包": ["T恤", "卫衣", "外套", "鞋", "包", "袜子", "帽"],
        "美妆个护": ["面膜", "口红", "洗发", "护肤", "香水", "剃须"],
        "食品饮料": ["零食", "饮料", "咖啡", "茶", "牛奶", "坚果"],
        "母婴玩具": ["奶粉", "尿不湿", "玩具", "婴儿", "童装"],
        "其他": [],
    },
    "browser": {
        "headless": False,
        "user_data_dir": ".browser_profile",
        "page_load_timeout": 30,
        "request_interval": [1.5, 3.5],
    },
    "output": {
        "dir": "output",
        "excel": True,
        "json": True,
        "images_dir": "output/images",
    },
}


# 列定义
COL_CHECK, COL_PLATFORM, COL_TITLE, COL_PRICE, COL_TYPE, COL_BUCKET, COL_IMG, COL_URL = range(8)
HEADERS = ["选择", "平台", "标题", "价格", "类型", "价格区间", "图片数", "链接"]

ALL_TAB = "全部"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Product Scraper · 1688 / 拼多多 商品批量抓取")
        self.resize(1320, 860)
        self.setMinimumSize(1100, 720)

        self.cfg = self._load_cfg()
        self.products: list[Product] = []        # 全部抓到的
        self.worker: ScrapeWorker | None = None

        # 把 scraper 内部的 loguru 日志全部接到 GUI 日志面板（v0.3.0 修复）
        self._log_bridge = LogBridge.instance()
        self._log_bridge.log.connect(self._log)

        self._build_ui()

    # =================== 配置 ===================
    def _load_cfg(self) -> dict:
        cfg_path = Path("config.yaml")
        if cfg_path.exists():
            try:
                with cfg_path.open("r", encoding="utf-8") as f:
                    user = yaml.safe_load(f) or {}
                merged = {**DEFAULT_CFG, **user}
                # 嵌套 dict 合并
                for k in ("browser", "output", "type_rules"):
                    if k in user:
                        merged[k] = {**DEFAULT_CFG[k], **user[k]}
                return merged
            except Exception:
                pass
        return DEFAULT_CFG.copy()

    # =================== UI ===================
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(self._build_param_box())

        # 中间区域：分类 Tab + 表格
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._build_table_box())
        splitter.addWidget(self._build_log_box())
        splitter.setSizes([580, 200])
        root.addWidget(splitter, 1)

        root.addWidget(self._build_action_bar())

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("就绪")

    # ---- 顶部参数区 ----
    def _build_param_box(self) -> QGroupBox:
        box = QGroupBox("抓取参数")
        lay = QVBoxLayout(box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("关键词："))
        self.ed_keywords = QLineEdit(", ".join(self.cfg.get("keywords") or []))
        self.ed_keywords.setPlaceholderText("用逗号分隔，例如：蓝牙耳机, 充电宝, 保温杯")
        row1.addWidget(self.ed_keywords, 3)

        row1.addWidget(QLabel("URL："))
        self.ed_urls = QLineEdit("")
        self.ed_urls.setPlaceholderText("可选：直接给商品详情链接，多个用空格分隔")
        row1.addWidget(self.ed_urls, 2)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        self.cb_1688 = QCheckBox("1688")
        self.cb_1688.setChecked("alibaba1688" in self.cfg["platforms"])
        self.cb_pdd = QCheckBox("拼多多")
        self.cb_pdd.setChecked("pinduoduo" in self.cfg["platforms"])
        row2.addWidget(QLabel("平台："))
        row2.addWidget(self.cb_1688)
        row2.addWidget(self.cb_pdd)
        row2.addSpacing(20)

        row2.addWidget(QLabel("每词数量："))
        self.sp_limit = QSpinBox()
        self.sp_limit.setRange(1, 500)
        self.sp_limit.setValue(int(self.cfg.get("per_keyword_limit", 30)))
        row2.addWidget(self.sp_limit)

        row2.addWidget(QLabel("翻页："))
        self.sp_pages = QSpinBox()
        self.sp_pages.setRange(1, 20)
        self.sp_pages.setValue(int(self.cfg.get("max_pages", 2)))
        row2.addWidget(self.sp_pages)

        self.cb_dl_img = QCheckBox("下载图片")
        self.cb_dl_img.setChecked(bool(self.cfg.get("download_images", True)))
        row2.addWidget(self.cb_dl_img)

        self.cb_headless = QCheckBox("无头浏览器（不推荐）")
        self.cb_headless.setChecked(bool(self.cfg["browser"].get("headless", False)))
        row2.addWidget(self.cb_headless)

        row2.addStretch()

        self.btn_start = QPushButton("▶  开始抓取")
        self.btn_start.setObjectName("primary")
        self.btn_start.clicked.connect(self._on_start)
        row2.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹  停止")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop)
        row2.addWidget(self.btn_stop)

        lay.addLayout(row2)

        row3 = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        row3.addWidget(self.progress, 1)
        lay.addLayout(row3)

        return box

    # ---- 中部：分类 Tab + 表格 ----
    def _build_table_box(self) -> QGroupBox:
        box = QGroupBox("商品列表（按类别分类）")
        lay = QVBoxLayout(box)

        # 价格区间过滤
        bucket_row = QHBoxLayout()
        bucket_row.addWidget(QLabel("价格区间："))
        self.cmb_bucket = QComboBox()
        self.cmb_bucket.addItem(ALL_TAB)
        for b in self.cfg["price_buckets"]:
            self.cmb_bucket.addItem(b["name"])
        self.cmb_bucket.currentIndexChanged.connect(self._refresh_table)
        bucket_row.addWidget(self.cmb_bucket)
        bucket_row.addStretch()

        self.lbl_summary = QLabel("共 0 件 · 已选 0 件")
        self.lbl_summary.setStyleSheet("color:#8B949E;")
        bucket_row.addWidget(self.lbl_summary)
        lay.addLayout(bucket_row)

        # 分类 Tab（按"类型"切换）
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._refresh_table)
        # 预先创建占位 Tab（每个 type_rules 的 key），抓取后再重建
        self._rebuild_tabs(initial=True)
        lay.addWidget(self.tabs)

        # 表格
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self._on_row_double_clicked)
        self.table.itemChanged.connect(self._on_item_changed)

        h = self.table.horizontalHeader()
        h.setSectionResizeMode(COL_CHECK, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(COL_PLATFORM, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(COL_TITLE, QHeaderView.Stretch)
        h.setSectionResizeMode(COL_PRICE, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(COL_TYPE, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(COL_BUCKET, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(COL_IMG, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(COL_URL, QHeaderView.Stretch)

        lay.addWidget(self.table, 1)
        return box

    def _rebuild_tabs(self, initial: bool = False) -> None:
        """根据当前已抓数据重建『类型』Tab。"""
        self.tabs.blockSignals(True)
        # 清空
        while self.tabs.count():
            self.tabs.removeTab(0)
        # 全部
        self.tabs.addTab(QWidget(), f"{ALL_TAB} ({len(self.products)})")
        # 每个类型一个 Tab，按数据动态生成
        type_counts: dict[str, int] = {}
        for p in self.products:
            t = p.bucket_type or "未分类"
            type_counts[t] = type_counts.get(t, 0) + 1
        # 先按 type_rules 顺序，未出现在 type_rules 的放后面
        ordered = [t for t in self.cfg["type_rules"].keys() if t in type_counts]
        ordered += [t for t in type_counts.keys() if t not in ordered]
        for t in ordered:
            self.tabs.addTab(QWidget(), f"{t} ({type_counts[t]})")
        if initial and self.tabs.count() == 1:
            # 抓取前给个占位
            for t in self.cfg["type_rules"].keys():
                self.tabs.addTab(QWidget(), f"{t} (0)")
        self.tabs.blockSignals(False)

    # ---- 底部：一键操作 ----
    def _build_action_bar(self) -> QGroupBox:
        box = QGroupBox("一键操作")
        lay = QHBoxLayout(box)

        self.btn_select_all = QPushButton("☑  一键全选（当前视图）")
        self.btn_select_all.clicked.connect(lambda: self._set_check_for_visible(True))
        lay.addWidget(self.btn_select_all)

        self.btn_unselect_all = QPushButton("☐  一键全不选")
        self.btn_unselect_all.clicked.connect(lambda: self._set_check_for_visible(False))
        lay.addWidget(self.btn_unselect_all)

        self.btn_invert = QPushButton("⇅  反选")
        self.btn_invert.clicked.connect(self._invert_visible)
        lay.addWidget(self.btn_invert)

        self.btn_select_all_global = QPushButton("☑  全选所有类别")
        self.btn_select_all_global.clicked.connect(lambda: self._set_check_for_all(True))
        lay.addWidget(self.btn_select_all_global)

        lay.addStretch()

        self.btn_open_out = QPushButton("📁  打开输出目录")
        self.btn_open_out.clicked.connect(self._open_output_dir)
        lay.addWidget(self.btn_open_out)

        self.btn_export = QPushButton("📤  一键导出选中（按类别分Sheet）")
        self.btn_export.setObjectName("primary")
        self.btn_export.clicked.connect(self._on_export)
        lay.addWidget(self.btn_export)

        return box

    # ---- 底部：日志 ----
    def _build_log_box(self) -> QGroupBox:
        box = QGroupBox("运行日志")
        lay = QVBoxLayout(box)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        f = QFont("Consolas")
        f.setStyleHint(QFont.Monospace)
        self.log_view.setFont(f)
        lay.addWidget(self.log_view)
        return box

    # =================== 抓取 ===================
    def _collect_cfg(self) -> dict:
        cfg = {**self.cfg}
        cfg["keywords"] = [s.strip() for s in self.ed_keywords.text().split(",") if s.strip()]
        cfg["urls"] = [s.strip() for s in self.ed_urls.text().split() if s.strip()]
        platforms = []
        if self.cb_1688.isChecked():
            platforms.append("alibaba1688")
        if self.cb_pdd.isChecked():
            platforms.append("pinduoduo")
        cfg["platforms"] = platforms
        cfg["per_keyword_limit"] = self.sp_limit.value()
        cfg["max_pages"] = self.sp_pages.value()
        cfg["download_images"] = self.cb_dl_img.isChecked()
        cfg["browser"] = {**self.cfg["browser"], "headless": self.cb_headless.isChecked()}
        return cfg

    def _on_start(self) -> None:
        cfg = self._collect_cfg()
        if not cfg["platforms"]:
            QMessageBox.warning(self, "参数错误", "请至少勾选一个平台。")
            return
        if not cfg["keywords"] and not cfg["urls"]:
            QMessageBox.warning(self, "参数错误", "请至少填写关键词或 URL。")
            return

        # 重置
        self.products.clear()
        self.table.setRowCount(0)
        self._rebuild_tabs(initial=True)
        self._update_summary()
        self.progress.setValue(0)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._log("INFO", "开始抓取 ...")
        self._log("INFO", "提示：浏览器会先打开各平台首页确认登录。如果跳出登录页，请在弹出的浏览器窗口中扫码 / 登录后，回到本程序点对话框里的【已完成】。")

        self.worker = ScrapeWorker(cfg)
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self._on_progress)
        self.worker.product_done.connect(self._on_product_done)
        self.worker.finished_ok.connect(self._on_worker_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.user_login_required.connect(self._on_user_login_required)
        self.worker.start()

    def _on_user_login_required(self, platform: str, message: str) -> None:
        """worker 检测到登录页 → 弹模态对话框，等用户点【已完成】或【取消】。"""
        zh = {"alibaba1688": "1688", "pinduoduo": "拼多多"}.get(platform, platform)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(f"需要登录 - {zh}")
        box.setText(message)
        btn_done = box.addButton("✅ 已完成，继续抓取", QMessageBox.AcceptRole)
        btn_cancel = box.addButton("❌ 取消，跳过该平台", QMessageBox.RejectRole)
        box.setDefaultButton(btn_done)
        box.exec()

        if not self.worker:
            return
        if box.clickedButton() is btn_done:
            self._log("INFO", f"[{zh}] 用户确认登录完成，继续抓取。")
            self.worker.proceed_login()
        else:
            self._log("WARN", f"[{zh}] 用户取消登录。")
            self.worker.cancel_login()

    def _on_stop(self) -> None:
        if self.worker:
            self.worker.stop()
            self._log("WARN", "请求停止...")

    def _on_progress(self, cur: int, total: int, msg: str) -> None:
        if total > 0:
            self.progress.setValue(int(cur / total * 100))
        self.status.showMessage(msg)

    def _on_product_done(self, p: Product) -> None:
        self.products.append(p)
        self._rebuild_tabs()
        self._refresh_table()

    def _on_worker_finished(self, products: list) -> None:
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress.setValue(100)
        self._log("INFO", f"抓取完成，共 {len(self.products)} 件商品。")

    def _on_worker_failed(self, err: str) -> None:
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._log("ERROR", err)
        QMessageBox.critical(self, "抓取失败", err)

    # =================== 表格 ===================
    def _current_type_filter(self) -> str | None:
        idx = self.tabs.currentIndex()
        if idx < 0:
            return None
        text = self.tabs.tabText(idx)
        # 形如 "数码电器 (10)" → "数码电器"
        name = text.rsplit(" (", 1)[0]
        return None if name == ALL_TAB else name

    def _current_bucket_filter(self) -> str | None:
        v = self.cmb_bucket.currentText()
        return None if v == ALL_TAB else v

    def _filtered(self) -> list[Product]:
        t = self._current_type_filter()
        b = self._current_bucket_filter()
        out = []
        for p in self.products:
            if t is not None and (p.bucket_type or "未分类") != t:
                continue
            if b is not None and (p.bucket_price or "未知") != b:
                continue
            out.append(p)
        return out

    def _refresh_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for p in self._filtered():
            row = self.table.rowCount()
            self.table.insertRow(row)

            chk = QTableWidgetItem()
            chk.setFlags(chk.flags() | Qt.ItemIsUserCheckable)
            chk.setCheckState(Qt.Checked)
            chk.setData(Qt.UserRole, p.product_id + ":" + p.platform)
            self.table.setItem(row, COL_CHECK, chk)

            self.table.setItem(row, COL_PLATFORM, _ro(p.platform))
            self.table.setItem(row, COL_TITLE, _ro(p.title or ""))
            price_str = f"￥{p.price:.2f}" if p.price is not None else (p.price_text or "-")
            self.table.setItem(row, COL_PRICE, _ro(price_str))
            self.table.setItem(row, COL_TYPE, _ro(p.bucket_type or "-"))
            self.table.setItem(row, COL_BUCKET, _ro(p.bucket_price or "-"))
            self.table.setItem(row, COL_IMG, _ro(str(len(p.images))))
            self.table.setItem(row, COL_URL, _ro(p.url))
        self.table.blockSignals(False)
        self._update_summary()

    def _on_item_changed(self, _item) -> None:
        self._update_summary()

    def _on_row_double_clicked(self, item) -> None:
        row = item.row()
        url_item = self.table.item(row, COL_URL)
        if url_item:
            QDesktopServices.openUrl(QUrl(url_item.text()))

    def _set_check_for_visible(self, checked: bool) -> None:
        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):
            it = self.table.item(r, COL_CHECK)
            if it:
                it.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.table.blockSignals(False)
        self._update_summary()

    def _invert_visible(self) -> None:
        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):
            it = self.table.item(r, COL_CHECK)
            if it:
                it.setCheckState(
                    Qt.Unchecked if it.checkState() == Qt.Checked else Qt.Checked
                )
        self.table.blockSignals(False)
        self._update_summary()

    def _set_check_for_all(self, checked: bool) -> None:
        """全选所有产品（不限当前 Tab/区间）。"""
        # 把当前视图全选；同时把"未在视图但已勾选"标记保留下来。
        # 简化：直接维护一份全局选中集合。
        self._select_all = checked
        self._global_check_state = {p.product_id + ":" + p.platform: checked
                                     for p in self.products}
        self._refresh_table_with_global_state()

    def _refresh_table_with_global_state(self) -> None:
        self._refresh_table()
        if not getattr(self, "_global_check_state", None):
            return
        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):
            it = self.table.item(r, COL_CHECK)
            key = it.data(Qt.UserRole) if it else None
            if key and key in self._global_check_state:
                it.setCheckState(
                    Qt.Checked if self._global_check_state[key] else Qt.Unchecked
                )
        self.table.blockSignals(False)
        self._update_summary()

    def _update_summary(self) -> None:
        total = len(self.products)
        selected = self._collect_selected_keys()
        self.lbl_summary.setText(f"共 {total} 件 · 已选 {len(selected)} 件")

    def _collect_selected_keys(self) -> set[str]:
        """从当前表格收集勾选项 key（仅当前视图）。"""
        keys: set[str] = set()
        for r in range(self.table.rowCount()):
            it = self.table.item(r, COL_CHECK)
            if it and it.checkState() == Qt.Checked:
                k = it.data(Qt.UserRole)
                if k:
                    keys.add(k)
        return keys

    # =================== 导出 ===================
    def _on_export(self) -> None:
        if not self.products:
            QMessageBox.information(self, "提示", "还没有抓到商品。")
            return

        # 收集"全部已勾选"的商品：以当前视图为准 + 全局映射
        # 这里采用：让用户在当前视图勾选 → 我们再合并所有 Tab 中曾勾选的状态有点重，
        # 简化成：导出当前 Tab 内勾选项 + 历史全选过的项。
        keys_visible = self._collect_selected_keys()
        keys = set(keys_visible)
        if getattr(self, "_global_check_state", None):
            keys |= {k for k, v in self._global_check_state.items() if v}

        if not keys:
            QMessageBox.information(self, "提示", "请先勾选要导出的商品（或点『一键全选』）。")
            return

        out_dir = QFileDialog.getExistingDirectory(
            self, "选择导出目录",
            str(Path(self.cfg["output"].get("dir", "output")).resolve())
        )
        if not out_dir:
            return

        chosen: list[Product] = [
            p for p in self.products
            if (p.product_id + ":" + p.platform) in keys
        ]
        # 兜底：如果选的商品还没分类，再分一次
        classify_products(chosen, self.cfg["type_rules"], self.cfg["price_buckets"])

        out_cfg = {**self.cfg["output"], "dir": out_dir,
                    "images_dir": str(Path(out_dir) / "images")}
        storage = Storage(out_cfg)

        try:
            if self.cb_dl_img.isChecked():
                self._log("INFO", f"开始下载选中商品图片到 {out_dir}/images ...")
                storage.download_images_for(chosen)
            paths = storage.save(chosen)
            msg = "\n".join(f"{k.upper()}: {v}" for k, v in paths.items())
            self._log("INFO", f"导出完成：\n{msg}")
            ret = QMessageBox.information(
                self, "导出完成",
                f"已导出 {len(chosen)} 件商品（按类别 + 价格区间分 Sheet）\n\n{msg}\n\n是否打开输出目录？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if ret == QMessageBox.Yes:
                QDesktopServices.openUrl(QUrl.fromLocalFile(out_dir))
        except Exception as exc:  # noqa: BLE001
            self._log("ERROR", f"导出失败：{exc}")
            QMessageBox.critical(self, "导出失败", str(exc))

    def _open_output_dir(self) -> None:
        d = Path(self.cfg["output"].get("dir", "output")).resolve()
        d.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))

    # =================== 日志 ===================
    def _log(self, level: str, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        color = {
            "INFO": "#8B949E",
            "WARN": "#D29922",
            "ERROR": "#F85149",
        }.get(level, "#E6EDF3")
        line = f'<span style="color:#666;">[{ts}]</span> ' \
               f'<span style="color:{color};">[{level}]</span> {msg}'
        self.log_view.appendHtml(line)

    # =================== 关闭 ===================
    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        super().closeEvent(event)


def _ro(text: str) -> QTableWidgetItem:
    """生成只读单元格."""
    it = QTableWidgetItem(text)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it
