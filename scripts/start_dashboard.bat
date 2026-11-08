@echo off
echo ========================================================
echo   Physical AI with Isaac / Gemini - Dashboard Launcher
echo ========================================================
echo.
echo Starting Unified Server (Port 3001)...
start cmd /k "cd ..\gemini_web_gui && node server.cjs"

echo.
echo Waiting for server to initialize...
timeout /t 1 /nobreak > nul

echo Opening dashboard in default browser...
start http://localhost:3001/

echo.
echo Done! Keep the terminal window open while using the dashboard.
echo You can now use the "Start" button in the browser to launch ROS 2.
pause
