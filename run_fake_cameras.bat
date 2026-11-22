@echo off
REM Streams 4 fake cameras to the local server.
REM Usage: run_fake_cameras.bat                 (uses the Ultralytics sample picture)
REM        run_fake_cameras.bat videos\front.mp4 (same video on all 4 positions)
cd /d "%~dp0server"
if "%~1"=="" (
  "%~dp0.venv\Scripts\python.exe" tools\fake_camera.py --all --image sample
) else (
  "%~dp0.venv\Scripts\python.exe" tools\fake_camera.py --all --video "%~f1"
)
