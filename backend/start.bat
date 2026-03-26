@echo off
title Dridha Weed Detection Server
color 0A
echo.
echo  ██████╗ ██████╗ ██╗██████╗ ██╗  ██╗ █████╗
echo  ██╔══██╗██╔══██╗██║██╔══██╗██║  ██║██╔══██╗
echo  ██║  ██║██████╔╝██║██║  ██║███████║███████║
echo  ██║  ██║██╔══██╗██║██║  ██║██╔══██║██╔══██║
echo  ██████╔╝██║  ██║██║██████╔╝██║  ██║██║  ██║
echo  ╚═════╝ ╚═╝  ╚═╝╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
echo.
echo  Weed Detection System - Backend Server
echo  ----------------------------------------

cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist ".deps_installed" (
    echo [SETUP] Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
    echo installed > .deps_installed
    echo [SETUP] Done!
)

REM Check model file
if not exist "best.pt" (
    echo [WARN] best.pt not found in this folder!
    echo [WARN] Copy your YOLO model file here as best.pt
    echo.
)

echo [START] Launching Dridha server on http://localhost:8000
echo [INFO]  Open the dashboard UI in your browser
echo [INFO]  Press Ctrl+C to stop
echo.
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
pause
