@echo off
chcp 65001 >nul
REM WeChat Article Agent - DEMO Launcher (batch version)
REM Usage: double-click or run start.bat

setlocal
set "PROJECT_ROOT=%~dp0"
set "BACKEND=%PROJECT_ROOT%backend"
set "FRONTEND=%PROJECT_ROOT%frontend"

echo ========================================
echo   WeChat Article Agent - DEMO Launcher
echo ========================================

REM Check DeepSeek API Key
if "%DEEPSEEK_API_KEY%"=="" (
    echo [WARN] DEEPSEEK_API_KEY env var not set
    set /p "APIKEY=Enter DeepSeek API Key (or press Enter to skip): "
    if not "%APIKEY%"=="" set "DEEPSEEK_API_KEY=%APIKEY%"
)

REM Start backend
echo.
echo [1/2] Starting backend (http://localhost:8000)...
start "WA-Backend" powershell -NoExit -Command "cd '%BACKEND%'; $env:DEEPSEEK_API_KEY='%DEEPSEEK_API_KEY%'; uvicorn main:app --reload --port 8000"

REM Start frontend
echo [2/2] Starting frontend (http://localhost:5173)...
start "WA-Frontend" powershell -NoExit -Command "cd '%FRONTEND%'; npx http-server . -p 5173 -c-1 --cors"

echo.
echo ========================================
echo   Started!
echo   Frontend: http://localhost:5173
echo   Backend docs: http://localhost:8000/docs
echo ========================================
echo.
pause
