#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python3 -c "import PySide6" 2>/dev/null || pip install -r requirements.txt
python3 -u invoice_app.py
