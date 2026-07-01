@echo off
setlocal
cd /d "%~dp0"

if not exist ".env" (
  echo No .env file found. Mythos will still start, but voice AI needs OPENAI_API_KEY.
  echo Create .env from README_DESKTOP.md when you are ready.
)

python desktop_launcher.py --start
if errorlevel 1 (
  echo.
  echo Mythos could not start. Check .mythos_runtime\streamlit.log for details.
  pause
  exit /b 1
)

endlocal
