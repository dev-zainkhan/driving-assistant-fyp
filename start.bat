@echo off
REM Starts the server (new window, port 8000) and the Next.js dashboard (this window, port 3000).
REM Run setup.bat once before this.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo [ERROR] Run setup.bat first. & exit /b 1)
if not exist "clients\node_modules" (echo [ERROR] Run setup.bat first. & exit /b 1)
netstat -ano | findstr /r /c:":8000 .*LISTENING" >nul && (echo [ERROR] Port 8000 is already in use: close the old server window first. & exit /b 1)
netstat -ano | findstr /r /c:":3000 .*LISTENING" >nul && (echo [ERROR] Port 3000 is already in use: close the old dashboard window first. & exit /b 1)

echo Starting the server in a new window (http://localhost:8000) ...
start "Driving Assistant server" cmd /k "cd /d "%~dp0server" && "%~dp0.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws-per-message-deflate false"

echo Waiting for the AI model to load ...
"%~dp0.venv\Scripts\python.exe" server\tools\wait_for_server.py || exit /b 1

echo Building and starting the dashboard (http://localhost:3000) ...
cd clients
call npm run build:next || exit /b 1
start "" http://localhost:3000
call npm run start -w nextjs-web
endlocal
