@echo off
REM ==========================================
REM  Kraken Klash 单机模拟器 打包脚本 (Windows)
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
if not exist .venv-sim (
  python -m venv .venv-sim
)
call .venv-sim\Scripts\activate.bat

echo [3/4] 安装最小依赖（不装主仓库的重型依赖）...
pip install --upgrade pip -q
pip install typer==0.12.5 rich==13.9.4 questionary==2.0.1 pyyaml==6.0.2 -q
pip install pyinstaller==6.11.1 -q

echo [4/4] 打包 KrakenKlashSim.exe...
if exist dist-sim rmdir /s /q dist-sim
if exist build-sim rmdir /s /q build-sim
pyinstaller kraken-klash-sim.spec --clean --noconfirm --distpath dist-sim --workpath build-sim

if exist dist-sim\KrakenKlashSim.exe (
  echo.
  echo ============================================
  echo  构建成功！
  echo  可执行文件: dist-sim\KrakenKlashSim.exe
  echo  双击即可启动交互模式
  echo ============================================
  explorer dist-sim
) else (
  echo 构建失败，检查上方错误信息
  exit /b 1
)

endlocal
