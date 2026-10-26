@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo 사용법: REVIEW.bat 소스.cpp
  echo 또는: REVIEW.bat 소스폴더
  pause
  exit /b 1
)
py -3 "%~dp0cli.py" %*
pause
