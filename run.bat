@echo off
rem One-step launcher for Windows: creates a virtual environment, installs requirements, starts the console.
cd /d "%~dp0"
if not exist .venv ( py -3 -m venv .venv || python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
python run_gui.py %*
