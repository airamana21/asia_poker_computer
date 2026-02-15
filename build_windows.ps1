#!/usr/bin/env pwsh
# One-click build script for Windows

Write-Host "Asia Poker 4-2-1 Windows Build Script" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python not found in PATH" -ForegroundColor Red
    exit 1
}

Write-Host "`n[1/5] Checking virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

Write-Host "`n[2/5] Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

Write-Host "`n[3/5] Installing dependencies..." -ForegroundColor Yellow
pip install -q -r requirements.txt
pip install -q pyinstaller

Write-Host "`n[4/5] Generating card assets..." -ForegroundColor Yellow
python -c "from src.gui.assets import ensure_assets; ensure_assets()"

Write-Host "`n[5/5] Building executable with PyInstaller..." -ForegroundColor Yellow
pyinstaller --clean --noconfirm build_windows.spec

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✓ Build completed successfully!" -ForegroundColor Green
    Write-Host "Executable: dist\AsiaPoker421\AsiaPoker421.exe" -ForegroundColor Green
    Write-Host "`nTo distribute, zip the entire dist\AsiaPoker421 folder." -ForegroundColor Cyan
} else {
    Write-Host "`n✗ Build failed!" -ForegroundColor Red
    exit 1
}
