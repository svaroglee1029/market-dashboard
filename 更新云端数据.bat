@echo off
chcp 65001 >nul
title Update Cloud Dashboard Data
echo ==================================================
echo   Cloud Dashboard Data Update Tool
echo ==================================================
echo.
echo Steps:
echo   1. Export latest data from local MySQL
echo   2. Compress and commit to GitHub
echo   3. Streamlit Cloud auto-update (~3-5 min)
echo.
echo Prerequisites: MySQL running, proxy enabled
echo ==================================================
echo.

cd /d "C:\Users\lic12\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6a656234af2d53a124a81126"

set HTTPS_PROXY=http://127.0.0.1:7897
set HTTP_PROXY=http://127.0.0.1:7897

python update_cloud.py

echo.
echo ==================================================
echo Dashboard: https://market-dashboard-m5.streamlit.app
echo ==================================================
echo.
pause