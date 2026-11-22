@echo off
REM Install for laptops WITHOUT an NVIDIA graphics card (about 1 GB download).
cd /d "%~dp0"
py -3.12 -m venv .venv || (echo Python 3.12 not found. Install it from python.org first. & pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu || (pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install -r server\requirements.txt || (pause & exit /b 1)
cd clients
call npm install || (echo Node.js not found. Install Node.js 20+ from nodejs.org first. & pause & exit /b 1)
echo.
echo Done. Now run run_server.bat, then run_nextjs.bat
pause
