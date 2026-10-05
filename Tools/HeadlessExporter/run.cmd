@echo off
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Missing Python environment. Run setup commands from README.md first.
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0export_assets.py" %*
exit /b %ERRORLEVEL%
