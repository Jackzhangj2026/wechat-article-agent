@echo off
chcp 65001 >nul
title 停止服务
echo 正在停止 WeChat Article Agent 服务...
echo.

REM 杀死后端和前端进程
taskkill /f /im uvicorn.exe >nul 2>&1
taskkill /f /im node.exe >nul 2>&1
taskkill /f /im http-server.exe >nul 2>&1

echo [OK] 所有服务已停止
echo 你可以关闭此窗口了
echo.
pause