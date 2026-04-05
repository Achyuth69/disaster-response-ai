@echo off
title Disaster Response AI System
echo.
echo  ==========================================
echo   DISASTER RESPONSE AI SYSTEM
echo  ==========================================
echo.

cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from python.org
    pause
    exit /b 1
)

REM Check .env
if not exist ".env" (
    echo Creating .env from example...
    copy .env.example .env
    echo.
    echo IMPORTANT: Edit .env and add your GROQ_API_KEY
    echo Get free key at: https://console.groq.com
    echo.
    notepad .env
)

REM Install dependencies if needed
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo.
echo Starting server...
echo.
python run_api.py

pause
