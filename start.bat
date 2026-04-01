@echo off
title Loba Padel Income Monitor
echo ============================================
echo   Loba Padel - Income Monitor
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo Please download it from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM Install dependencies if needed
echo Checking dependencies...
pip install -r "%~dp0requirements.txt" --quiet
echo.

echo Starting the application...
echo Dashboard will open at: http://localhost:5000
echo.
echo Press Ctrl+C to stop the application.
echo ============================================
echo.

REM Open browser after a short delay
start "" /min cmd /c "timeout /t 3 >nul && start http://localhost:5000"

REM Start the app
python "%~dp0app.py"

pause
