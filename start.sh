#!/usr/bin/env bash
# Start der Rechnungspruefungs-App unter Linux/macOS
cd "$(dirname "$0")"
if [ ! -d venv ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
