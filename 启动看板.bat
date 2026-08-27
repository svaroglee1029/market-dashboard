@echo off
chcp 65001 >nul
title 市场分析仪表盘
echo ========================================
echo   市场分析仪表盘 - 启动中...
echo ========================================
echo.

:: 先清理旧进程
taskkill /f /im streamlit.exe >nul 2>&1
taskkill /f /im cloudflared.exe >nul 2>&1

:: 启动 Streamlit（后台）
cd /d "C:\Users\lic12\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6a656234af2d53a124a81126"
start /b "" python -m streamlit run dashboard.py --server.port=8501 --server.address=127.0.0.1 --server.headless=true

echo 等待 Streamlit 启动...
timeout /t 8 /nobreak >nul

:: 启动 Cloudflare Tunnel
echo 启动公网隧道...
start /b "" C:\Users\lic12\cloudflared.exe tunnel --url http://localhost:8501

timeout /t 8 /nobreak >nul
echo.
echo ========================================
echo   仪表盘已启动！
echo   本地访问: http://localhost:8501
echo   公网链接: 请查看上方 trycloudflare.com 地址
echo ========================================
echo.
echo   注意: 关闭此窗口将停止服务
echo   公网链接每次启动会变化
echo.
pause
