# Automated Setup Script for Windows (PowerShell)
# Bulk Job Website -> Excel Extractor

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Setting up Bulk Job Website -> Excel Extractor" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Ensure Python 3.12+ is installed
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found in PATH. Attempting installation via winget..." -ForegroundColor Yellow
    winget install --id Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

# 2. Ensure Node.js LTS is installed
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js not found in PATH. Attempting installation via winget..." -ForegroundColor Yellow
    winget install --id OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

# 3. Create Python virtual environment
Write-Host "`n[1/4] Setting up Python virtual environment..." -ForegroundColor Green
if (-not (Test-Path "backend\.venv")) {
    python -m venv backend\.venv
}

# 4. Install backend dependencies
Write-Host "`n[2/4] Installing backend Python packages..." -ForegroundColor Green
& ".\backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\backend\.venv\Scripts\pip.exe" install -r backend\requirements.txt

# 5. Install Playwright Chromium browser
Write-Host "`n[3/4] Installing Playwright Chromium browser..." -ForegroundColor Green
& ".\backend\.venv\Scripts\playwright.exe" install chromium

# 6. Install Frontend dependencies
Write-Host "`n[4/4] Installing frontend npm packages..." -ForegroundColor Green
$env:PATH = "C:\Program Files\nodejs;" + $env:PATH
Set-Location frontend
& "C:\Program Files\nodejs\npm.cmd" install
Set-Location ..

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "Setup Completed Successfully!" -ForegroundColor Green
Write-Host "To run backend: .\backend\.venv\Scripts\python -m uvicorn backend.app.main:app --port 8000 --reload" -ForegroundColor White
Write-Host "To run frontend: cd frontend; npm run dev" -ForegroundColor White
Write-Host "==========================================" -ForegroundColor Cyan
