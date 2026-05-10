# ⚡ Chain Sniper

**多链链上狙击 · 打新 · 跟单 GUI 工具**

一个 exe 搞定 Solana / BNB Chain / Ethereum 上 16 个细分功能。

![build](https://github.com/icelist/icelist/actions/workflows/build-exe.yml/badge.svg)

---

## 🚀 快速下载（Windows）

**方式 1：从 Releases 下载**（推荐，带版本号）

打开 [Releases 页面](https://github.com/icelist/icelist/releases) → 下载最新版 `ChainSniper.exe`

**方式 2：从 Actions artifacts 下载**（最新构建，30 天内有效）

1. 打开 [Actions 页面](https://github.com/icelist/icelist/actions/workflows/build-exe.yml)
2. 点击最新的 ✅ 绿色 workflow run
3. 滚到底部 `Artifacts` 区域，下载 `ChainSniper-Windows-<sha>`
4. 解压得到 `ChainSniper.exe`，双击运行

> ⚠ 文件约 75MB。首次启动需要 10–20 秒解压，之后秒开。

---

## ✨ 功能一览

### Solana（6 个）
| 代号 | 功能 | 说明 |
|---|---|---|
| `sol.pumpfun` | 🔥 Pump.fun 早期狙击 | WebSocket 监听 Create 指令，代币诞生第一秒跟进 |
| `sol.pumpfun_grad` | 🔥 Pump.fun 毕业狙击 | 监控 bonding curve 接近 100%，转 Raydium 前抢入 |
| `sol.raydium` | 🎯 Raydium 新池狙击 | 监听 Raydium V4 / CPMM `initialize2` 事件 |
| `sol.meteora` | 🎯 Meteora DLMM 狙击 | 监听 DLMM 池创建 |
| `sol.jup_launchpad` | 🚀 JUP 打新 | Jupiter Studio / LFG Launchpad / DBC bonding curve |
| `sol.copytrade` | 👥 聪明钱跟单 | logsSubscribe 目标钱包 |

### BNB Chain（5 个）
| 代号 | 功能 |
|---|---|
| `bsc.pancake_v2` | PancakeSwap V2 新池狙击 |
| `bsc.pancake_v3` | PancakeSwap V3 新池狙击 |
| `bsc.fourmeme` | Four.meme 早期狙击 |
| `bsc.copytrade` | 聪明钱跟单 |
| `bsc.launchpad` | BNB IDO 打新 |

### Ethereum（5 个）
| 代号 | 功能 |
|---|---|
| `eth.uniswap_v2` | Uniswap V2 新池狙击 |
| `eth.uniswap_v3` | Uniswap V3 新池狙击 |
| `eth.virtuals` | Virtuals Protocol 新 Agent |
| `eth.copytrade` | 聪明钱跟单 |
| `eth.launchpad` | IDO 打新（Legion / Echo / CoinList） |

---

## 🖥 使用流程

### 首次启动（3 分钟配置）

1. **双击 `ChainSniper.exe`** 打开软件
2. 左侧导航进入 **「📡 API 设置」**
3. 点击 **「🔐 设置主密码」**（用于加密私钥，至少 6 位）
4. 填入至少一项 RPC 配置：
   - 推荐：`HELIUS_KEY`（Solana，免费 [helius.dev](https://helius.dev)）
   - 推荐：`ALCHEMY_ETH_KEY`（EVM，免费 [alchemy.com](https://alchemy.com)）
   - 或直接填 `SOL_RPC_URL` / `ETH_RPC_URL` / `BSC_RPC_URL`
5. 可选：填 Telegram Bot Token + Chat ID 接收交易通知
6. 点击 **「💾 保存全部」**
7. 左侧进入 **「🔑 钱包」**，导入专用狙击钱包私钥
   - Solana：base58 格式
   - EVM：0x 开头 64 位 hex 或纯 hex
8. 进入 **「⚡ 功能」**，点击任意功能卡片上的 **「▶ 启动」**

### 日常使用

- **「◉ 仪表盘」**：实时监控运行策略数、信号流、持仓 PnL
- **「📜 日志」**：实时日志流，可按级别过滤、导出为文件
- **「⏹ 停止全部」**（左下角）：一键关闭所有运行中的策略

---

## 🛡 安全设计

- ✅ **主密码永不落盘**，只在内存中，进程关闭即清除
- ✅ **私钥 + API Key** 通过 PBKDF2 (100,000 轮迭代) 派生密钥 + Fernet (AES-128-CBC + HMAC-SHA256) 加密
- ✅ 存储路径：`%USERPROFILE%\.chain-sniper\vault.dat`
- ✅ 错密码立即拒绝，无暴力破解可能
- ✅ 所有策略默认 **DRY_RUN 模式**（只检测不下单），需手动切换到实盘
- ✅ 内置代币安全检查：GoPlus (EVM) + Rugcheck (Solana)

---

## ⚠️ 风险提示

- **使用专用钱包**：永远不要导入主钱包私钥！建议新建一个小额钱包
- **先模拟再实盘**：至少跑 24 小时 DRY_RUN 观察信号质量
- **起手金额小**：实盘从 $10–20 开始，熟悉后再加码
- **狙击 ≠ 稳赚**：绝大多数 memecoin 会归零，Rug Pull 常见
- **RPC 速度决定胜负**：公共节点经常抢不到，建议付费节点（Helius Pro $99/月、QuickNode 等）
- **软件作者不对任何资金损失负责**

---

## 🏗 架构

```
chain-sniper/
├── app.py                    # GUI 入口
├── main.py                   # CLI 入口（保留）
├── chain-sniper.spec         # PyInstaller 打包配置
├── .github/workflows/        # 自动构建 Windows exe
│
├── core/                     # 核心层
│   ├── base.py              # 抽象基类 + SignalBus
│   ├── vault.py             # 加密保险箱 (PBKDF2 + Fernet)
│   ├── safety.py            # GoPlus + Rugcheck
│   ├── notifier.py          # Telegram + Discord
│   ├── config.py            # 配置加载（.env + Vault）
│   └── logger.py
│
├── chains/                   # 链客户端
│   ├── solana/client.py     # AsyncClient + Jupiter v6 + WS
│   └── evm/client.py        # AsyncWeb3 + Uniswap V2 Router
│
├── functions/                # 16 个功能
│   ├── solana_fns.py
│   ├── bsc_fns.py
│   └── eth_fns.py
│
└── gui/                      # PySide6 界面
    ├── main_window.py        # 主窗口 + 导航
    ├── theme.py              # 深色 QSS
    ├── runner.py             # 后台 asyncio 调度
    ├── log_bridge.py         # loguru → Qt Signal
    ├── pages/                # 5 个页面
    └── widgets/              # 卡片组件
```

---

## 🛠 从源码运行 / 开发

```bash
git clone https://github.com/icelist/icelist
cd icelist
pip install -r requirements.txt
python app.py
```

### 本地打包

- Windows: 双击 `build.bat`
- macOS / Linux: `chmod +x build.sh && ./build.sh`

详见 [BUILD.md](./BUILD.md)

---

## 📝 当前开发状态

### ✅ 已完成
- GUI 5 页面 + 深色主题 + 实时动画
- 加密保险箱（主密码 + Fernet）
- 16 个功能的注册、路由、UI 卡片
- Solana: Jupiter v6 quote/swap/sign/send、WebSocket program 订阅
- EVM: Uniswap V2 Router buy/sell、PairCreated 事件轮询
- GoPlus + Rugcheck 安全检查集成
- Telegram + Discord 通知
- GitHub Actions 自动构建 Windows exe + Release

### 🚧 待优化
- Jito bundle 提交（当前走普通 RPC，延迟略高）
- Meteora DLMM / four.meme / Virtuals 的指令解析更精准
- 每个 Launchpad（Legion / Binance Wallet）的合约具体接入
- 止盈 / 止损自动执行（框架已就绪）
- Alpha、Hyperliquid、Base 等更多链

---

## 🤝 贡献

发现 bug 或有想法 → 开 Issue / PR

---

## 📄 许可

PySide6 采用 LGPL，可自由分发与商用。本项目代码采用 MIT 协议。
