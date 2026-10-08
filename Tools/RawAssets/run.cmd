@echo off
setlocal
if not defined UMA_RAW_PYTHON set "UMA_RAW_PYTHON=%~dp0..\HeadlessExporter\.venv\Scripts\python.exe"
if exist "%UMA_RAW_PYTHON%" (
  "%UMA_RAW_PYTHON%" -X utf8 -B "%~dp0uma_raw.py" %*
) else (
  python -X utf8 -B "%~dp0uma_raw.py" %*
)
exit /b %errorlevel%
