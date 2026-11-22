@echo off
REM Zain's Next.js dashboard: builds it, then serves it on http://localhost:3000
REM (also reachable from other devices on the Wi-Fi at http://<laptop-ip>:3000).
REM The server (run_server.bat or run_demo.bat) must be running too.
cd /d "%~dp0clients"
call npm run build:next || (echo Next.js build failed & pause & exit /b 1)
call npm run start -w nextjs-web
