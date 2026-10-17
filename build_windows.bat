@echo off
setlocal enabledelayedexpansion

echo =========================================================
echo   Building CyberHazardLab Standalone Windows Application
echo =========================================================

REM Move to script directory
cd /d "%~dp0"

REM Check for virtual environment or system Python
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
    set "PYINSTALLER=.venv\Scripts\pyinstaller.exe"
) else (
    set "PYTHON=python"
    set "PYINSTALLER=pyinstaller"
)

echo [*] Checking dependencies...
%PYTHON% -m pip install -r requirements.txt
%PYTHON% -m pip install pyinstaller

echo [*] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [*] Compiling standalone Windows distribution...
%PYINSTALLER% --clean --noconfirm cyberhazardlab.spec

echo.
echo =========================================================
echo   Build Finished!
echo =========================================================
echo Application Folder: dist\CyberHazardLab\
echo Executable:         dist\CyberHazardLab\CyberHazardLab.exe
echo.
pause
