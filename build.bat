@echo off
REM ==========================================
REM  Chain Sniper 打包脚本 (Windows)
REM  出错时窗口会保留，用户可查看日志
REM ==========================================
setlocal EnableDelayedExpansion

REM 切到脚本所在目录
cd /d "%~dp0"

echo ============================================
echo   Chain Sniper - Windows Build
echo ============================================
echo.
echo Working dir: %CD%
echo.

REM ---------- [1/5] 检查 Python ----------
echo [1/5] Checking Python installation...
set "PY_CMD="

REM 优先尝试 py launcher（官方 Python 安装包自带）
where py >nul 2>nul
if %errorlevel%==0 (
  for /f "tokens=*" %%i in ('py -3.11 --version 2^>nul') do set "PY_CMD=py -3.11"
  if "!PY_CMD!"=="" for /f "tokens=*" %%i in ('py -3.10 --version 2^>nul') do set "PY_CMD=py -3.10"
  if "!PY_CMD!"=="" for /f "tokens=*" %%i in ('py -3 --version 2^>nul') do set "PY_CMD=py -3"
)

REM 退回到 python
if "!PY_CMD!"=="" (
  where python >nul 2>nul
  if %errorlevel%==0 set "PY_CMD=python"
)

if "!PY_CMD!"=="" (
  echo [ERROR] Python not found!
  echo.
  echo Please install Python 3.10 or 3.11 from:
  echo   https://www.python.org/downloads/
  echo.
  echo IMPORTANT: During install, check the box:
  echo   [X] Add Python to PATH
  echo.
  goto :error
)

echo   Using: !PY_CMD!
for /f "tokens=*" %%i in ('!PY_CMD! --version') do echo   Version: %%i
echo.

REM ---------- [2/5] 创建虚拟环境 ----------
echo [2/5] Creating virtual environment...
if not exist .venv (
  !PY_CMD! -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create venv
    goto :error
  )
  echo   Created .venv
) else (
  echo   Using existing .venv
)
echo.

REM ---------- [3/5] 激活 venv 并升级 pip ----------
echo [3/5] Activating venv and upgrading pip...
call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo [ERROR] Failed to activate venv
  goto :error
)

python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
  echo [ERROR] Failed to upgrade pip
  goto :error
)
echo.

REM ---------- [4/5] 安装依赖 ----------
echo [4/5] Installing dependencies (this may take 3-5 minutes)...
pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [ERROR] Failed to install dependencies from requirements.txt
  echo         Check the error messages above.
  echo.
  echo Common fixes:
  echo   - Check your internet connection
  echo   - Try using a pip mirror:
  echo     pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  goto :error
)

pip install pyinstaller==6.11.1
if errorlevel 1 (
  echo [ERROR] Failed to install PyInstaller
  goto :error
)
echo.

REM ---------- [5/5] 打包 ----------
echo [5/5] Building ChainSniper.exe (this takes 1-3 minutes)...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

pyinstaller chain-sniper.spec --clean --noconfirm
if errorlevel 1 (
  echo.
  echo [ERROR] PyInstaller build failed.
  echo         Check the error messages above.
  goto :error
)

if not exist "dist\ChainSniper.exe" (
  echo.
  echo [ERROR] Build finished but ChainSniper.exe not found in dist\
  echo         Contents of dist\:
  dir dist
  goto :error
)

echo.
echo ============================================
echo   [OK] Build SUCCESS!
echo.
echo   Output: %CD%\dist\ChainSniper.exe
for %%A in ("dist\ChainSniper.exe") do echo   Size:   %%~zA bytes
echo ============================================
echo.
echo Opening dist folder...
explorer dist
echo.
echo Press any key to exit...
pause >nul
exit /b 0


:error
echo.
echo ============================================
echo   BUILD FAILED
echo ============================================
echo.
echo Please copy the errors above and share them for help.
echo.
echo Press any key to exit...
pause >nul
exit /b 1
