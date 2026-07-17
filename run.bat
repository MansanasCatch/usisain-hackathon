@echo off
title UsisAIn - Startup Script
echo ===================================================
echo             UsisAIn Startup Script
echo ===================================================

:: 1. Check if Ollama is running
echo [1/3] Checking Ollama service...
ollama list >nul 2>&1
if %errorlevel% equ 0 goto ollama_ok

echo [Ollama] Ollama is not running. Starting Ollama serve...
start "" ollama serve
echo [Ollama] Waiting for Ollama to initialize...

set /a count=0
:wait_ollama
timeout /t 2 >nul
ollama list >nul 2>&1
if %errorlevel% equ 0 goto ollama_ok
set /a count+=2
if %count% lss 10 goto wait_ollama

echo [Ollama] WARNING: Ollama took too long to start. Please make sure it is running manually.
goto continue_startup

:ollama_ok
echo [Ollama] Ollama is up and running!

:continue_startup
:: 2. Check and activate Virtual Environment
echo [2/3] Checking virtual environment...
if not exist "venv\Scripts\activate.bat" (
    echo [Error] Virtual environment not found in 'venv\'.
    echo Please create it first using: python -m venv venv
    pause
    exit /b 1
)

echo [Venv] Activating virtual environment...
call venv\Scripts\activate.bat

:: 3. Run the backend app
echo [3/3] Starting backend server on http://localhost:8000...
echo [Server] Press CTRL+C to stop the server.
cd backend-api
uvicorn usisain_backend.main:app --reload --app-dir src --host 0.0.0.0 --port 8000
pause
