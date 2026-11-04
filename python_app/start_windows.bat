@echo off
cd /d "%~dp0"
rem Prefer the Python 3.12 installed for this project; fall back to `python`.
set "PY=py -3.12"
py -3.12 -V >nul 2>nul
if errorlevel 1 set "PY=python"
echo Checking project dependencies...
%PY% -c "import pandas; assert pandas.__version__.split('.')[0] == '2'" >nul 2>nul
if errorlevel 1 %PY% -m pip install "pandas>=2.0,<3"
if errorlevel 1 (
  echo Dependency installation failed. Check your Python installation and internet connection.
  pause
  exit /b 1
)
echo Starting RecycleMatch HK ... open http://localhost:8501 in your browser.
%PY% web_app.py --open-browser
pause
