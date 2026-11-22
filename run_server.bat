@echo off
REM Starts the Driving Assistant server on all network interfaces, port 8000.
cd /d "%~dp0server"
"%~dp0.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws-per-message-deflate false
