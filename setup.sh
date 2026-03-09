#!/usr/bin/env bash
# Auto-install script for XAUUSD M15 Signal Engine
set -e

echo "================================================"
echo "  XAUUSD M15 Signal Engine - Setup"
echo "================================================"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3 is not installed. Please install Python 3.11+."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo "[OK] Python: $PYTHON_VERSION"

# Use pip from PATH (Replit uses .pythonlibs/bin/pip, not system pip)
if ! command -v pip &>/dev/null; then
    echo "[ERROR] pip is not available in PATH."
    exit 1
fi

PIP_VERSION=$(pip --version 2>&1)
echo "[OK] pip: $PIP_VERSION"

echo ""
echo "[INFO] Installing dependencies from requirements.txt..."
pip install -r requirements.txt --quiet

echo ""
echo "[OK] All dependencies installed."
echo ""

# Verify key packages
echo "[INFO] Verifying packages..."
python3 -c "import aiohttp; print(f'  [OK] aiohttp {aiohttp.__version__}')"
python3 -c "import websockets; print(f'  [OK] websockets {websockets.__version__}')"

echo ""
echo "================================================"
echo "  Setup complete! Run: python server.py"
echo "================================================"
