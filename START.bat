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
