@echo off
REM ==========================================
REM  Product Scraper 打包脚本 (Windows)
REM ==========================================
setlocal

cd /d %~dp0

echo [1/4] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo Please install Python 3.10+
  exit /b 1
)

echo [2/4] Creating venv...
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate.bat

echo [3/4] Installing deps...
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install pyinstaller==6.11.1 -q

echo [4/4] Building exe...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
pyinstaller product-scraper.spec --clean --noconfirm

if exist dist\ProductScraper.exe (
  echo.
  echo ============================================
  echo  Build OK!
  echo  Output: dist\ProductScraper.exe
  echo ============================================
  explorer dist
) else (
  echo Build FAILED, check errors above.
  exit /b 1
)

endlocal
