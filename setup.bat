@echo off
REM One-click install of everything (Python packages + dashboard packages).
REM Picks the GPU build of PyTorch if an NVIDIA card is found, else the CPU build.
REM Safe to run again: it skips what is already installed.
setlocal
cd /d "%~dp0"

where py >nul 2>nul || (echo [ERROR] Python launcher "py" not found. Install Python 3.12 from python.org ^(tick "Add to PATH"^). & exit /b 1)
py -3.12 --version >nul 2>nul || (echo [ERROR] Python 3.12 not found. Install Python 3.12 from python.org. & exit /b 1)
where npm >nul 2>nul || (echo [ERROR] Node.js not found. Install Node.js 20 LTS or newer from nodejs.org. & exit /b 1)

if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Creating Python environment .venv
  py -3.12 -m venv .venv || exit /b 1
) else (
  echo [1/4] Python environment .venv already exists
)
set PY="%~dp0.venv\Scripts\python.exe"
%PY% -m pip install --upgrade pip --quiet

set TORCH_INDEX=https://download.pytorch.org/whl/cpu
set KIND=CPU
where nvidia-smi >nul 2>nul && (set TORCH_INDEX=https://download.pytorch.org/whl/cu126& set KIND=GPU)
%PY% -c "import torch" >nul 2>nul && (
  echo [2/4] PyTorch already installed
) || (
  echo [2/4] Installing PyTorch 2.14 for %KIND% ^(CPU about 1 GB, GPU about 3 GB^)
  %PY% -m pip install torch==2.14.0 torchvision==0.29.0 --index-url %TORCH_INDEX% || exit /b 1
)

echo [3/4] Installing server packages
%PY% -m pip install -r server\requirements.txt --quiet || exit /b 1

echo [4/4] Installing dashboard packages
pushd clients
call npm install --no-audit --no-fund || (popd & exit /b 1)
popd

%PY% -c "import torch; print('PyTorch', torch.__version__, '| GPU:', torch.cuda.is_available())"
echo.
echo Setup done. Start everything with: start.bat
endlocal
