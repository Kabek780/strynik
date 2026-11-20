@echo off
setlocal
cd /d "%~dp0"

where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw "%~dp0main.py"
    exit /b 0
)

where python >nul 2>nul
if not errorlevel 1 (
    python "%~dp0main.py"
    exit /b %errorlevel%
)

echo Python 3.10+ not found. Install Python and run:
echo     python -m pip install -r requirements.txt
pause
exit /b 1
