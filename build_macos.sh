#!/usr/bin/env bash
# One-click build script for macOS

set -e

echo "Asia Poker 4-2-1 macOS Build Script"
echo "===================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found in PATH"
    exit 1
fi

echo -e "\n[1/5] Checking virtual environment..."
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo -e "\n[2/5] Activating virtual environment..."
source .venv/bin/activate

echo -e "\n[3/5] Installing dependencies..."
pip install -q -r requirements.txt
pip install -q pyinstaller

echo -e "\n[4/5] Generating card assets..."
python -c "from src.gui.assets import ensure_assets; ensure_assets()"

echo -e "\n[5/5] Building app bundle with PyInstaller..."
pyinstaller --clean --noconfirm build_macos.spec

if [ $? -eq 0 ]; then
    echo -e "\n✓ Build completed successfully!"
    echo "Application: dist/AsiaPoker421.app"
    echo -e "\nTo distribute, create a DMG or zip the .app bundle."
    echo "Note: For Gatekeeper compatibility, consider code signing."
else
    echo -e "\n✗ Build failed!"
    exit 1
fi
