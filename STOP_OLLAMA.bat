@echo off
cd /d "%~dp0"
echo BAT: %~f0
echo.

where ollama >nul 2>&1
if errorlevel 1 goto NO_OLLAMA

echo [1/4] 현재 로드된 모델 확인 (ollama ps)
echo -----------------------------------------
ollama ps
echo.

echo [2/4] ollama ps 목록을 파싱해 실행 중인 모델을 모두 중지합니다.
set "STOPPED=0"
for /f "skip=1 tokens=1" %%m in ('ollama ps 2^>nul') do (
  if not "%%m"=="" (
    echo 중지: %%m
    ollama stop "%%m"
    set "STOPPED=1"
  )
)
if "%STOPPED%"=="0" echo 실행 중인 모델이 없습니다.
echo.

echo [3/4] 대표 모델도 확인 후 중지합니다.
for %%m in (qwen3:14b qwen2.5-coder:7b llama3.1:8b) do (
  echo 중지 시도: %%m
  ollama stop "%%m" >nul 2>&1
)
echo.

echo [4/4] 중지 후 상태 확인 (ollama ps)
echo -----------------------------------------
ollama ps
echo.

REM 모델만 내린 뒤에도 ollama 서버 프로세스가 남아 있으면 정리
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | findstr /I "ollama.exe" >nul
if not errorlevel 1 (
  echo ollama.exe 프로세스가 남아 있어 종료합니다.
  taskkill /IM ollama.exe /F >nul 2>&1
  if errorlevel 1 (
    echo ollama.exe 종료에 실패했습니다. 작업 관리자에서 확인하세요.
  ) else (
    echo ollama.exe 프로세스를 종료했습니다.
  )
) else (
  echo 정리할 ollama.exe 프로세스가 없습니다.
)

echo.
echo Ollama 중지를 완료했습니다.
echo 확인: ollama ps
echo.
pause
exit /b 0

:NO_OLLAMA
echo Ollama가 설치되어 있지 않거나 PATH에 없습니다.
echo https://ollama.com/download 에서 설치한 뒤 다시 실행하세요.
pause
exit /b 1
