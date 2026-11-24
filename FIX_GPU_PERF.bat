@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul 2>&1

echo === 1080 Ti LLM GPU check ===
echo.

REM Ultimate Performance. Fallback: High performance.
powercfg /SETACTIVE e9a42b02-d5df-448d-aa00-03f14749eb61 >nul 2>&1
if errorlevel 1 (
  powercfg /SETACTIVE 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c >nul 2>&1
  echo Power plan: High performance
) else (
  echo Power plan: Ultimate Performance
)
powercfg /GETACTIVESCHEME
echo.

echo IMPORTANT: DemoForge Mirage Driver can lock GPU clocks.
echo If Mirage exists, open Device Manager - Display adapters
echo Right-click Mirage Driver - Disable device
echo.

echo NVIDIA Control Panel:
echo   Manage 3D settings - Program Settings
echo   Add ollama.exe and llama-server.exe
echo   Power management mode = Prefer maximum performance
echo.

echo During generation, healthy nvidia-smi looks like:
echo   power 100W+, graphics clock 1500MHz+, pstate P2/P0
echo   If power ~50W and clock ~700MHz, clocks are locked.
echo.

where nvidia-smi >nul 2>&1
if not errorlevel 1 (
  nvidia-smi --query-gpu=name,pstate,power.draw,clocks.gr,clocks.mem,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv
  echo.
  ollama ps 2>nul
  echo.
  echo Display devices:
  powershell -NoProfile -Command "Get-PnpDevice -Class Display | Select-Object Status,FriendlyName | Format-Table -AutoSize"
)

echo.
pause
endlocal
exit /b 0
