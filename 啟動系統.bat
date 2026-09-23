@echo off
cd /d "%~dp0"

echo Starting Carpool and Purchase Tracker, please wait...
start "Carpool and Purchase Tracker (do not close this window)" "venv\Scripts\python.exe" app.py

timeout /t 3 /nobreak >nul
start "" "http://localhost:5050"

echo.
echo System started. A browser window should open shortly.
echo To stop the system, close the other black window titled
echo "Carpool and Purchase Tracker".
echo This window can be closed directly.
echo.
pause
