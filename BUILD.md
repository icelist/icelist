# 打包为可执行文件

## Windows（生成 ChainSniper.exe）

1. 安装 Python 3.10+（勾选"Add to PATH"）
2. 双击 `build.bat`
3. 产物：`dist\ChainSniper.exe`（单文件，约 80-120MB）

## macOS（生成 ChainSniper.app）

```bash
chmod +x build.sh
./build.sh
open dist/ChainSniper.app
```

## Linux

```bash
chmod +x build.sh
./build.sh
./dist/ChainSniper
```

## 常见问题

### 1. exe 启动后秒退
打开 `chain-sniper.spec`，把 `console=False` 改成 `console=True`，重新打包，就能看到错误输出。

### 2. "Failed to execute script"
多半是某个依赖没被 PyInstaller 侦测到。在 `.spec` 的 `hiddenimports` 里加上对应模块名再构建。

### 3. 启动慢（10-30 秒）
单文件 exe 首次启动会解压到临时目录，慢是正常的。如果介意，改用目录模式（在 `.spec` 里把 `EXE` 那一段改成 `COLLECT`，产物是一个文件夹，启动瞬间打开）。

### 4. 杀毒软件报警
PyInstaller 打包的 exe 被误报很常见。可以：
- 给 exe 做代码签名（需要购买证书）
- 或者分发前把源码公开，让用户自己 build

### 5. 文件太大
- 启用 UPX 压缩（`.spec` 里 `upx=True`，先从 upx.github.io 下载 upx.exe 放到 PATH）
- 把不用的依赖从 `requirements.txt` 拆到 `requirements-dev.txt`
- 用 `--onedir` 模式代替 `--onefile`

## 数据存储位置

用户的私钥 / API Key 加密后保存在：

- **Windows**: `%USERPROFILE%\.chain-sniper\vault.dat`
- **macOS/Linux**: `~/.chain-sniper/vault.dat`

首次启动时会要求设置"主密码"，之后每次打开软件都要输入一次。私钥永不以明文落盘，也永不离开本机。

## 升级

重新跑 `build.bat` / `build.sh` 即可，保险箱文件不会被覆盖。
