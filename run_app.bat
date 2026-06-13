@echo off
REM ===========================================================================
REM  Goodtown Revenue Model Explorer - double-click launcher
REM  - First run: builds the .venv and installs dependencies automatically.
REM  - Every run: starts the app and opens it in your browser.
REM  Leave this console window open while you use the app; close it to stop.
REM ===========================================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\streamlit.exe" (
    echo First run detected - setting up the virtual environment...
    echo This takes a minute the first time only.
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    echo Setup complete.
    echo.
)

echo Starting Goodtown Revenue Model Explorer...
".venv\Scripts\streamlit.exe" run app.py

echo.
echo The app has stopped. Press any key to close this window.
pause >nul
