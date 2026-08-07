@echo off
chcp 65001 >nul
REM WeChat Article Agent - 双击静默启动（无 PowerShell 黑窗口）
set "ROOT=%~dp0"

REM 启动后端（隐藏窗口）
start /min "" powershell -WindowStyle Hidden -NoExit -Command "cd '%ROOT%backend'; uvicorn main:app --reload --port 8001"

REM 等待 3 秒等后端启动
timeout /t 3 /nobreak >nul

REM 启动前端（隐藏窗口）
start /min "" powershell -WindowStyle Hidden -NoExit -Command "cd '%ROOT%frontend'; npx http-server . -p 5173 -c-1 --cors"

REM 打开浏览器
start http://localhost:5173

exit