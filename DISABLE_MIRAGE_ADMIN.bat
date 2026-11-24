@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul 2>&1

net session >nul 2>&1
if errorlevel 1 (
  echo Run this file as Administrator.
  echo Right-click - Run as administrator
  pause
  exit /b 1
)

echo === Remove DemoForge Mirage Driver ===
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-PnpDevice -Class Display | Format-Table Status,FriendlyName,InstanceId -AutoSize; ^
   try { Disable-PnpDevice -InstanceId 'ROOT\DISPLAY\0000' -Confirm:$false -ErrorAction Stop; 'Mirage disabled' } catch { $_.Exception.Message }; ^
   pnputil /remove-device ROOT\DISPLAY\0000; ^
   $inf = (Get-WmiObject Win32_PnPSignedDriver | Where-Object { $_.DeviceName -eq 'Mirage Driver' }).InfName; ^
   if ($inf) { 'Deleting ' + $inf; pnputil /delete-driver $inf /uninstall /force }; ^
   Get-PnpDevice -Class Display | Format-Table Status,FriendlyName -AutoSize"

echo.
echo Now set NVIDIA Control Panel for BOTH:
echo   ollama.exe
echo   llama-server.exe
echo Power management mode = Prefer maximum performance
echo.
echo Then restart Ollama and run a review again.
echo During generation check: power 100W+ and clock 1500MHz+
echo.
pause
endlocal
exit /b 0
