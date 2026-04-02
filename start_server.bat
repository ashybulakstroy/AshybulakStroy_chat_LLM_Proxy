@echo off
setlocal
cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" run.py
  exit /b %errorlevel%
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" run.py
  exit /b %errorlevel%
)

echo Virtual environment python was not found in venv or .venv.
echo Run venv\Scripts\python.exe run.py or create the virtual environment first.
exit /b 1
