#!/usr/bin/env bash
# Auto-install script for XAUUSD M15 Signal Engine
set -e

echo "================================================"
echo "  XAUUSD M15 Signal Engine - Setup"
echo "================================================"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3 is not installed."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo "[OK] Python: $PYTHON_VERSION"

# Install pip if missing
if ! python3 -m pip --version &>/dev/null; then
    echo "[INFO] Installing pip..."
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3
fi

echo "[INFO] Installing dependencies from requirements.txt..."
python3 -m pip install --upgrade pip --quiet
python3 -m pip install -r requirements.txt --quiet

echo ""
echo "[OK] All dependencies installed."
echo ""

# Verify key packages
echo "[INFO] Verifying packages..."
python3 -c "import aiohttp; print(f'  aiohttp {aiohttp.__version__}')"
python3 -c "import websockets; print(f'  websockets {websockets.__version__}')"

echo ""
echo "================================================"
echo "  Setup complete! Run: python server.py"
echo "================================================"
