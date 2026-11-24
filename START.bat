@echo off
cd /d "%~dp0"
REM 로컬 폐쇄망: 텔레메트리·HF 온라인 체크 차단, Ollama 루프백 고정
set ANONYMIZED_TELEMETRY=False
set CHROMA_TELEMETRY=False
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set HF_DATASETS_OFFLINE=1
set OLLAMA_HOST=127.0.0.1:11434
echo BAT: %~f0
echo APP: %~dp0app.py
echo MODEL: qwen2.5-coder:7b
echo URL: http://127.0.0.1:8501
echo SECURITY: HF/Chroma offline + Streamlit stats off
echo.

REM GPU가 35W/700MHz에 멈추면 LLM이 급격히 느려진다. 최고의 성능 전원으로 올린다.
powercfg /SETACTIVE e9a42b02-d5df-448d-aa00-03f14749eb61 >nul 2>&1
if errorlevel 1 powercfg /SETACTIVE 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c >nul 2>&1

REM WDDM이 CUDA를 Idle로 오인하면 클럭이 700MHz에 묶인다. WPF는 -STA 필수.
start "GPU-Wake" powershell.exe -STA -NoProfile -ExecutionPolicy Bypass -File "%~dp0GPU_WAKE.ps1"

where py >nul 2>&1
if errorlevel 1 goto NO_PY

py -3 -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto NO_PIP

where cppcheck >nul 2>&1
if errorlevel 1 echo cppcheck? ????. ?? ? ?? ???? 1? ??? ?????.

where ollama >nul 2>&1
if errorlevel 1 goto NO_OLLAMA

ollama list | findstr /I "qwen2.5-coder:7b" >nul
if errorlevel 1 (
  echo qwen2.5-coder:7b 모델을 받습니다.
  ollama pull qwen2.5-coder:7b
  if errorlevel 1 goto NO_MODEL
)

py -3 -m streamlit run "%~dp0app.py"
exit /b 0

:NO_PY
echo Python ??? py ? ?? ?????.
pause
exit /b 1

:NO_PIP
echo ??? ??? ??????.
pause
exit /b 1

:NO_OLLAMA
echo Ollama? ???? ?? ????.
echo https://ollama.com/download ?? ??? ? ? ??? ?? ?????.
pause
exit /b 1

:NO_MODEL
echo ?? ????? ??????.
pause
exit /b 1
