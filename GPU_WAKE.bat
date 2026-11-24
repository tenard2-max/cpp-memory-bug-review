@echo off
cd /d "%~dp0"
chcp 65001 >nul 2>&1
echo Starting GPU wake window. Leave it open during review.
start "GPU Wake" powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0GPU_WAKE.ps1"
exit /b 0
