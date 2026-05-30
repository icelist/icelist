#!/bin/bash
# Kraken Klash 单机模拟器 打包脚本 (macOS / Linux)
set -e

cd "$(dirname "$0")"

echo "[1/4] 检查 Python..."
python3 --version || { echo "请安装 Python 3.10+"; exit 1; }

echo "[2/4] 创建虚拟环境..."
if [ ! -d .venv-sim ]; then
  python3 -m venv .venv-sim
fi
# shellcheck disable=SC1091
source .venv-sim/bin/activate

echo "[3/4] 安装最小依赖..."
pip install --upgrade pip -q
pip install typer==0.12.5 rich==13.9.4 questionary==2.0.1 pyyaml==6.0.2 -q
pip install pyinstaller==6.11.1 -q

echo "[4/4] 打包..."
rm -rf dist-sim build-sim
pyinstaller kraken-klash-sim.spec --clean --noconfirm --distpath dist-sim --workpath build-sim

if [ -f dist-sim/KrakenKlashSim ]; then
  echo ""
  echo "============================================"
  echo " 构建成功！"
  echo " 产物: ./dist-sim/KrakenKlashSim"
  echo " 直接运行: ./dist-sim/KrakenKlashSim"
  echo "============================================"
  ls -lh dist-sim/
else
  echo "构建失败"
  exit 1
fi
