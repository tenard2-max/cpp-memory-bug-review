@echo off
cd /d "%~dp0"
chcp 65001 >nul 2>&1
echo This will ask for Administrator permission.
echo After success you MUST reboot.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_force_powermizer.ps1"
exit /b %ERRORLEVEL%
