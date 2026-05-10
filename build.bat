@echo off
REM ==========================================
REM  Chain Sniper 打包脚本 (Windows)
REM ==========================================
setlocal

cd /d %~dp0

echo [1/4] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo 请先安装 Python 3.10+
  exit /b 1
)

echo [2/4] 创建虚拟环境（如不存在）...
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate.bat

echo [3/4] 安装依赖...
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install pyinstaller -q

echo [4/4] 打包 exe...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
pyinstaller chain-sniper.spec --clean --noconfirm

if exist dist\ChainSniper.exe (
  echo.
  echo ============================================
  echo  构建成功！
  echo  可执行文件: dist\ChainSniper.exe
  echo ============================================
  explorer dist
) else (
  echo 构建失败，检查上方错误信息
  exit /b 1
)

endlocal
