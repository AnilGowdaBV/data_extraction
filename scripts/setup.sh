#!/usr/bin/env bash
set -e

echo "=========================================="
echo "Setting up Bulk Job Extractor (Linux/macOS)"
echo "=========================================="

# Check Python 3.12+
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed. Please install Python 3.12+."
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "Node.js is required but not installed. Please install Node.js LTS."
    exit 1
fi

# 1. Virtual Environment
echo "[1/4] Setting up Python virtual environment..."
python3 -m venv backend/.venv
source backend/.venv/bin/activate

# 2. Python Dependencies
echo "[2/4] Installing backend dependencies..."
pip install --upgrade pip
pip install -r backend/requirements.txt

# 3. Playwright Chromium
echo "[3/4] Installing Playwright Chromium browser..."
playwright install chromium

# 4. Frontend Dependencies
echo "[4/4] Installing frontend npm dependencies..."
cd frontend
npm install
cd ..

echo "=========================================="
echo "Setup Complete!"
echo "Backend: source backend/.venv/bin/activate && uvicorn backend.app.main:app --port 8000 --reload"
echo "Frontend: cd frontend && npm run dev"
echo "=========================================="
