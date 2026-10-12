#!/usr/bin/env bash
# UsisAIn Launcher for macOS
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "====================================================="
echo "                UsisAIn for macOS                   "
echo "====================================================="

PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Error: Python 3 is required. Please install Python 3.11 or newer."
    echo "You can install it via Homebrew: brew install python"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    "$PYTHON" -m venv venv
    echo "Installing dependencies..."
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
    if [ ! -f ".env" ] && [ -f ".env.example" ]; then
        cp .env.example .env
    fi
    ./venv/bin/python data/scripts/init_db.py
fi

echo "Starting UsisAIn..."
./venv/bin/python run.py "$@"
