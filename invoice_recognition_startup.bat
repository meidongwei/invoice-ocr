@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Invoice OCR - Start
echo ========================================
echo.

set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 1>nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 1>nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    where python3 >nul 2>nul
    if not errorlevel 1 (
        python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 1>nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=python3"
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] Python 3.10+ not found.
    echo.
    echo Install from: https://www.python.org/downloads/
    echo Check: Add python.exe to PATH
    echo Then open a NEW cmd window and run this bat again.
    echo.
    echo If still failing, disable Store aliases:
    echo   Settings - Apps - App execution aliases
    echo   Turn OFF python.exe / python3.exe
    echo.
    pause
    exit /b 1
)

echo Using: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

set "PIP_OPTS=--index-url https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --timeout 120 --retries 10"

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

echo [2/3] Checking dependencies...
python -c "import PySide6" 1>nul 2>nul
if errorlevel 1 (
    echo Installing dependencies, first time may take minutes...
    python -m pip install %PIP_OPTS% --upgrade pip
    python -m pip install %PIP_OPTS% -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        echo.
        echo This is usually a network timeout while downloading packages.
        echo Please try again, or switch to another network / hotspot.
        pause
        exit /b 1
    )
    echo ok> ".venv\.deps_ok"
) else if not exist ".venv\.deps_ok" (
    echo Installing remaining dependencies...
    python -m pip install %PIP_OPTS% -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        echo.
        echo This is usually a network timeout while downloading packages.
        echo Please try again, or switch to another network / hotspot.
        pause
        exit /b 1
    )
    echo ok> ".venv\.deps_ok"
) else (
    echo Dependencies already installed.
)

echo [3/3] Starting app...
echo.
python -u invoice_app.py
if errorlevel 1 (
    echo.
    echo [ERROR] App exited with error. See messages above.
    pause
)

endlocal
