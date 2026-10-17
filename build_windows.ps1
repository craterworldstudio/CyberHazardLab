# CyberHazardLab Standalone Windows Build Script
$ErrorActionPreference = "Stop"

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "  Building CyberHazardLab Standalone Windows Application" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$Python = "python"
if (Test-Path ".venv\Scripts\python.exe") {
    $Python = ".venv\Scripts\python.exe"
}

Write-Host "[*] Installing/verifying requirements and PyInstaller..." -ForegroundColor Yellow
& $Python -m pip install -r requirements.txt
& $Python -m pip install pyinstaller

if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

Write-Host "[*] Compiling with PyInstaller..." -ForegroundColor Yellow
& $Python -m PyInstaller --clean --noconfirm cyberhazardlab.spec

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "  Build Successful!" -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "Distribution Directory: dist\CyberHazardLab\"
Write-Host "Binary Executable:      dist\CyberHazardLab\CyberHazardLab.exe"
