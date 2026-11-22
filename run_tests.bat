@echo off
REM Runs the server tests (pytest) and the dashboard tests (Vitest). No GPU needed.
cd /d "%~dp0server"
"%~dp0.venv\Scripts\python.exe" -m pytest || (pause & exit /b 1)
cd /d "%~dp0clients"
call npm test
pause
