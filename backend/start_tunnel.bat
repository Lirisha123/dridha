@echo off
title Dridha - ngrok Tunnel
color 0B
echo.
echo  DRIDHA - Public URL Tunnel
echo  ---------------------------
echo  This exposes your local backend to the internet
echo  so the Vercel UI can connect to it from anywhere.
echo.

REM Check if ngrok is installed
where ngrok >nul 2>&1
if errorlevel 1 (
    echo [ERROR] ngrok not found.
    echo.
    echo  Steps to install:
    echo  1. Go to https://ngrok.com/download
    echo  2. Create a FREE account
    echo  3. Download ngrok.exe and put it in this folder
    echo  4. Run: ngrok config add-authtoken YOUR_TOKEN
    echo  5. Then run this file again
    echo.
    pause
    exit /b 1
)

echo [INFO] Starting ngrok tunnel on port 8000...
echo [INFO] Copy the https:// URL shown below
echo [INFO] Paste it into your Vercel dashboard as VITE_API_URL
echo [INFO] Then redeploy your Vercel project
echo.
ngrok http 8000
pause
