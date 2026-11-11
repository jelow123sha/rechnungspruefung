@echo off
rem Start der Rechnungspruefungs-App unter Windows
cd /d "%~dp0"
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
