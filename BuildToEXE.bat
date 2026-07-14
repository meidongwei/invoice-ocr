@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Invoice OCR - Build EXE
echo ========================================
echo.
echo This script must run on a PC with Python 3.10+
echo First build needs network, about 10-30 minutes.
echo Output: dist\发票识别\发票识别.exe
echo.

set "PYTHON_CMD="

rem Prefer Python Launcher
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 1>nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

rem Fallback: python
if not defined PYTHON_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" 1>nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=python"
    )
)

rem Fallback: python3
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
    echo Please install Python from:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT during install:
    echo   [x] Add python.exe to PATH
    echo Then CLOSE this window, open a NEW cmd, and run this bat again.
    echo.
    echo Also disable Store aliases if needed:
    echo   Settings - Apps - Advanced app settings - App execution aliases
    echo   Turn OFF "python.exe" and "python3.exe"
    echo.
    pause
    exit /b 1
)

echo Using: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

set "PIP_OPTS=--index-url https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn --timeout 120 --retries 10"

if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [1/5] Virtual environment already exists.
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [2/5] Installing dependencies...
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

echo [3/5] Preparing OCR models...
python -c "from invoice_core import warmup_ocr_engine; warmup_ocr_engine(print); print('models ready')"
if errorlevel 1 (
    echo [WARN] Model warmup failed. Build continues.
)

echo [4/5] Cleaning old build...
if exist "build\invoice_app_windows" rmdir /s /q "build\invoice_app_windows"
if exist "dist\发票识别" rmdir /s /q "dist\发票识别"

echo [5/5] Building EXE, please wait...
python -m PyInstaller --noconfirm invoice_app_windows.spec
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Please send the error text above.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   BUILD OK
echo ========================================
echo.
echo EXE path:
echo   %cd%\dist\发票识别\发票识别.exe
echo.
echo How to use:
echo   1. Copy the whole folder "发票识别"
echo   2. Double-click 发票识别.exe
echo   3. Users do NOT need Python
echo.

if exist "dist\发票识别\发票识别.exe" (
    explorer "dist\发票识别"
)

pause
endlocal
