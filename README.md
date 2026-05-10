# Chain Sniper

多链链上狙击 / 打新 / 跟单 GUI 工具。一个 exe 搞定 Solana / BNB Chain / Ethereum 上 16 个细分功能。

## ✨ 特性

- 🎨 **现代化深色 GUI**（PySide6 / Qt 6.10，原生性能）
- 🔐 **加密保险箱**（主密码 PBKDF2 + Fernet 加密本地存储私钥和 API Key）
- 🎯 **16 个细分功能**，按链分类：
  - **Solana (6)** — Pump.fun 早期/毕业、Raydium、Meteora、JUP 打新、聪明钱跟单
  - **BNB Chain (5)** — PancakeSwap V2/V3、Four.meme、跟单、BNB 打新
  - **Ethereum (5)** — Uniswap V2/V3、Virtuals、跟单、IDO 打新
- 📊 **实时仪表盘** — 运行中策略数、信号流、持仓 PnL
- 📜 **实时日志** — 可按级别过滤、导出
- 🛡 **双运行模式** — DRY_RUN（只监测不下单）/ LIVE（实盘）
- 📦 **一键打包** — Windows `.exe` / macOS `.app` / Linux 二进制

## 🚀 快速开始

### 源码运行

```bash
pip install -r requirements.txt
python app.py
```

### 打包成可执行文件

```bash
# Windows
build.bat

# macOS / Linux
chmod +x build.sh
./build.sh
```

产物在 `dist/` 下。详见 [BUILD.md](./BUILD.md)。

## 🖥 使用流程

1. **首次启动** → 在「API 设置」页点击「设置主密码」创建保险箱
2. **配置 RPC** → 填入 Solana / ETH / BSC 的 RPC URL（推荐 Helius / Alchemy / QuickNode）
3. **导入钱包** → 「钱包」页添加狙击钱包私钥（⚠ 不要用主钱包！）
4. **启动功能** → 「功能」页点击任一卡片的「▶ 启动」按钮
5. **监控** → 「仪表盘」查看信号流和持仓，「日志」查看详细运行日志

## 🗂 架构

```
chain-sniper/
├── app.py                  # GUI 入口
├── main.py                 # CLI 入口（保留）
├── chain-sniper.spec       # PyInstaller 打包配置
├── build.bat / build.sh    # 一键打包脚本
│
├── gui/                    # PySide6 界面
│   ├── main_window.py
│   ├── theme.py            # 深色主题 QSS
│   ├── runner.py           # 后台 asyncio 调度
│   ├── log_bridge.py       # loguru → Qt Signal
│   ├── pages/              # 5 个页面
│   │   ├── dashboard_page.py
│   │   ├── functions_page.py
│   │   ├── wallets_page.py
│   │   ├── api_page.py
│   │   └── logs_page.py
│   └── widgets/
│       └── cards.py        # 卡片组件
│
├── core/
│   ├── base.py             # 抽象基类
│   ├── config.py
│   ├── logger.py
│   ├── notifier.py
│   └── vault.py            # ⭐ 加密保险箱
│
├── chains/                 # 链客户端
│   ├── solana/client.py
│   └── evm/client.py
│
└── functions/              # 16 个细分功能
    ├── solana_fns.py
    ├── bsc_fns.py
    └── eth_fns.py
```

## 🛡 安全

- ✅ 主密码 **永不落盘**，只在内存中保存
- ✅ 私钥使用 **Fernet (AES-128)** 加密，密钥通过 PBKDF2 (100k iterations) 派生
- ✅ API Key 与私钥一起加密
- ✅ 保险箱关闭 / 重启后必须重新输入主密码才能读取
- ⚠ 使用**专用狙击钱包**，永远不要导入主钱包私钥
- ⚠ 本软件仅供学习研究，链上交易风险自负

## 📝 当前开发状态

- ✅ **GUI 框架**：主窗口、5 页面、导航、深色主题、卡片组件
- ✅ **加密保险箱**：密码派生、加密存储、钱包 / API 管理
- ✅ **后台调度器**：asyncio 线程、功能启停
- ✅ **实时日志桥**：loguru → Qt Signal
- ✅ **打包配置**：PyInstaller spec + Windows/macOS/Linux 构建脚本
- 🚧 **策略真实逻辑**：16 个功能的 `_main_loop` 仍是 stub（log + sleep），等待填充
  - 优先级：`sol.pumpfun` + `sol.jup_launchpad`（共用 Jupiter API 和 Jito bundle）

## 📄 许可

本项目采用 PySide6（LGPL），可自由分发、商用，前提是保留 Qt 的版权声明。
