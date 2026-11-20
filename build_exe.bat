@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python 3.10+ not found.
    pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo Building PrintScheduler.exe...
python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name PrintScheduler ^
    --icon "assets\app.ico" ^
    --collect-all pymupdf ^
    main.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Done: %~dp0dist\PrintScheduler.exe
pause
