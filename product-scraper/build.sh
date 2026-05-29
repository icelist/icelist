#!/bin/bash
# Product Scraper 打包脚本 (macOS / Linux)
set -e

cd "$(dirname "$0")"

echo "[1/4] Checking Python..."
python3 --version || { echo "Please install Python 3.10+"; exit 1; }

echo "[2/4] Creating venv..."
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[3/4] Installing deps..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install pyinstaller==6.11.1 -q

echo "[4/4] Building..."
rm -rf dist build
pyinstaller product-scraper.spec --clean --noconfirm

if [ -f dist/ProductScraper ] || [ -d dist/ProductScraper.app ]; then
  echo ""
  echo "============================================"
  echo " Build OK! Output is in ./dist/"
  echo "============================================"
  ls -lh dist/
else
  echo "Build FAILED"
  exit 1
fi
