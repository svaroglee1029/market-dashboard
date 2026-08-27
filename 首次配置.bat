@echo off
chcp 65001 >nul
title 首次配置 - GitHub 认证
echo ╔══════════════════════════════════════════════╗
echo ║   首次配置：GitHub 账号认证                    ║
echo ╚══════════════════════════════════════════════╝
echo.
echo 此脚本只需运行一次，完成后以后更新数据无需再认证。
echo.
echo 即将打开浏览器，请用 GitHub 账号登录授权。
echo.
echo 按任意键开始...
pause >nul

cd /d "C:\Users\lic12\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6a656234af2d53a124a81126"

:: 设置代理
set HTTPS_PROXY=http://127.0.0.1:7897
set HTTP_PROXY=http://127.0.0.1:7897

:: 配置 Git Credential Manager
git config credential.helper manager

:: 触发认证（会打开浏览器）
echo.
echo 正在连接 GitHub，请在弹出的浏览器中登录...
echo.
git push origin main

echo.
echo ========================================
if %ERRORLEVEL% EQU 0 (
    echo ✅ 认证成功！以后可直接运行「更新云端数据.bat」
) else (
    echo ❌ 认证失败，请检查：
    echo   1. 代理是否开启（Clash/V2Ray，端口 7897）
    echo   2. GitHub 账号是否正确
    echo   3. 网络是否正常
)
echo ========================================
echo.
pause
