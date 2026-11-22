@echo off
REM Install for laptops WITH an NVIDIA graphics card (about 3 GB download).
REM CUDA 12.6 build: the newest one that still supports GTX 10xx (Pascal). Do not use cu128 or newer.
cd /d "%~dp0"
py -3.12 -m venv .venv || (echo Python 3.12 not found. Install it from python.org first. & pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cu126 || (pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install -r server\requirements.txt || (pause & exit /b 1)
".venv\Scripts\python.exe" -c "import torch; print('GPU found:', torch.cuda.is_available())"
cd clients
call npm install || (echo Node.js not found. Install Node.js 20+ from nodejs.org first. & pause & exit /b 1)
echo.
echo Done. Now run run_server.bat, then run_nextjs.bat
pause
