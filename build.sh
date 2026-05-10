#!/bin/bash
# Chain Sniper 打包脚本 (macOS / Linux)
set -e

cd "$(dirname "$0")"

echo "[1/4] 检查 Python..."
python3 --version || { echo "请安装 Python 3.10+"; exit 1; }

echo "[2/4] 创建虚拟环境..."
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[3/4] 安装依赖..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install pyinstaller -q

echo "[4/4] 打包..."
rm -rf dist build
pyinstaller chain-sniper.spec --clean --noconfirm

if [ -f dist/ChainSniper ] || [ -d dist/ChainSniper.app ]; then
  echo ""
  echo "============================================"
  echo " 构建成功！产物在 ./dist/"
  echo "============================================"
  ls -lh dist/
else
  echo "构建失败"
  exit 1
fi
