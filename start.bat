@echo off
chcp 65001 >nul
REM WeChat Article Agent - 启动后端服务（一个端口搞定前后端）
set "ROOT=%~dp0"

REM 启动后端（隐藏窗口）
start /min "" powershell -WindowStyle Hidden -NoExit -Command "cd '%ROOT%backend'; uvicorn main:app --reload --port 8001"

REM 等待 5 秒等后端启动
timeout /t 5 /nobreak >nul

REM 打开浏览器（自动重定向到前端页面）
start http://localhost:8001/

exit