# 🏗 打包指南

> 你不必自己打包！推送代码后 **GitHub Actions 自动打** Windows / macOS 二进制。
> 本文档面向想本地构建或理解流程的开发者。

---

## 📥 直接下载（最快）

### Windows `.exe`

**最新稳定版（Release）**

[点此下载 →](https://github.com/icelist/icelist/releases/latest)

**最新开发版（每个 commit 都会自动打包）**

1. 打开 [Actions](https://github.com/icelist/icelist/actions/workflows/build-exe.yml)
2. 点击最上面的 ✅ workflow run
3. 下拉到底部 `Artifacts`，下载 `ChainSniper-Windows-<sha>`
4. 解压得到 `ChainSniper.exe` → 双击即可

### macOS `.app`

只有打 tag 时才会构建。[Releases 页面](https://github.com/icelist/icelist/releases)下载 `ChainSniper-macOS.tar.gz`，解压双击 `ChainSniper.app`。

> 首次打开可能被 Gatekeeper 拦截：右键 `.app` → 打开 → 继续。

---

## 💻 本地打包

### 通用前置

- Python 3.10 或 3.11（不要用 3.12+，部分依赖兼容性待验证）
- `git clone https://github.com/icelist/icelist`

### Windows

双击 `build.bat` 即可，脚本会自动：

1. 创建虚拟环境 `.venv\`
2. `pip install -r requirements.txt + pyinstaller`
3. `pyinstaller chain-sniper.spec --clean --noconfirm`
4. 产物在 `dist\ChainSniper.exe`

### macOS / Linux

```bash
chmod +x build.sh
./build.sh
```

产物在 `dist/ChainSniper`（Linux）或 `dist/ChainSniper.app`（macOS）。

---

## 🤖 CI 自动化

`.github/workflows/build-exe.yml` 配置了 3 种触发条件：

| 触发 | 行为 |
|---|---|
| 推送到 `main` / `master` | 自动打 Windows exe，上传 artifact（30 天保留） |
| Pull Request | 自动跑导入测试 + 打包（验证改动不破坏 build） |
| 打 tag `v*`（如 `v0.2.0`） | 打 Windows exe + macOS app，**自动创建 GitHub Release 并上传** |
| 手动触发 (`workflow_dispatch`) | 同上全跑 |

### 发布新版流程

```bash
git tag v0.2.0 -m "Release 0.2.0"
git push origin v0.2.0
```

CI 会自动：
1. 在 Windows runner 打 exe
2. 在 macOS runner 打 .app
3. 创建 Release 页，附上两个产物
4. 生成 "What's Changed" changelog

---

## 🔧 打包问题排查

### 1. exe 启动即退出

spec 里把 `console=False` 改为 `console=True`，重新打包，用命令行运行即可看到 Python 报错。

### 2. `ModuleNotFoundError`

某个动态 import 模块被 PyInstaller 漏检。解决：在 `chain-sniper.spec` 的 `THIRDPARTY_HIDDEN` 列表里添加该模块名。

### 3. 杀毒软件误报

PyInstaller exe 被 Windows Defender 误报是**很常见**的（因为走的是 Python 自解压 bootloader，签名模式像 dropper）。

**解决方案（按推荐度）**：

- ❤️ 把 exe 加入 Windows Defender 白名单（设置 → 病毒和威胁防护 → 添加排除）
- ❤️ 从源码自己 `build.bat` 打包（你自己机器上的 exe 不会被误报）
- 🪙 为 exe 买代码签名证书（$100–400/年，彻底解决但贵）

### 4. 打出来的 exe 太大（80MB+）

正常。PySide6 Qt 本体就有 50MB+，加上 Python 运行时和各种库，80MB 是合理体积。如果特别介意：

- 切到 onedir 模式（`.spec` 的 EXE 改成 COLLECT），产物是文件夹但启动快
- 去掉用不到的模块（比如不打算用 CLI → 删 `ui/` 目录和 `rich`/`questionary`/`pyfiglet` 依赖）

### 5. macOS 打包后 "app is damaged"

Apple Gatekeeper 要求签名。未签名的 app 用户必须：

```bash
xattr -cr /Applications/ChainSniper.app
```

或右键 → 打开 → 继续。

---

## 📦 构建产物位置

### Windows
- 开发版: `dist\ChainSniper.exe`
- 用户数据: `%USERPROFILE%\.chain-sniper\`
  - `vault.dat` — 加密的私钥 + API Key
  - `vault.meta` — 盐值

### macOS
- 开发版: `dist/ChainSniper.app`
- 用户数据: `~/.chain-sniper/`

### Linux
- 开发版: `dist/ChainSniper`
- 用户数据: `~/.chain-sniper/`

---

## 🔐 升级不丢数据

用户数据存在 `~/.chain-sniper/`，和 exe 完全独立。所以：

- 下载新版 exe 直接替换旧版
- `vault.dat` 不会被覆盖
- 私钥、API Key、主密码继续可用

**完全卸载**：删除 exe + 删除 `~/.chain-sniper/` 目录即可。
