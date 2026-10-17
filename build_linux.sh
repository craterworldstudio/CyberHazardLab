#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Building CyberHazardLab Standalone Linux Application ==="

# Check for python / virtual environment
if [ -d ".venv" ]; then
    PYTHON=".venv/bin/python"
    PYINSTALLER=".venv/bin/pyinstaller"
else
    PYTHON="python3"
    PYINSTALLER="pyinstaller"
fi

if ! command -v "$PYINSTALLER" &>/dev/null && [ ! -f "$PYINSTALLER" ]; then
    echo "[!] PyInstaller not found. Installing into environment..."
    $PYTHON -m pip install pyinstaller
fi

# Clean previous build artifacts
rm -rf build dist

echo "[*] Running PyInstaller build..."
$PYINSTALLER --clean --noconfirm cyberhazardlab.spec

echo ""
echo "=== Build Complete! ==="
echo "Standalone application bundle: dist/CyberHazardLab/"
echo "Executable binary:             dist/CyberHazardLab/CyberHazardLab"
echo ""
echo "To run the application:"
echo "  ./dist/CyberHazardLab/CyberHazardLab"
