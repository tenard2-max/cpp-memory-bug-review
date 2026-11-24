@echo off
cd /d "%~dp0"
chcp 65001 >nul 2>&1
echo Starting GPU Turbo window. Leave it open during review.
start "GPU Turbo" powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0GPU_TURBO.ps1"
exit /b 0
