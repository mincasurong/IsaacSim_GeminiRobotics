@echo off
echo ========================================================
echo   Gemini Robotics ER - Monitoring Dashboard Launcher
echo ========================================================
echo.
echo Starting Backend Server (Port 3001)...
start cmd /k "cd ..\gemini_web_gui && node server.cjs"

echo Starting React GUI (Port 5173)...
start cmd /k "cd ..\gemini_web_gui && npm run dev -- --port 5173"

echo.
echo Waiting for servers to initialize...
timeout /t 3 /nobreak > nul

echo Opening dashboard in default browser...
start http://localhost:5173/

echo.
echo Done! Keep the two terminal windows open while using the dashboard.
echo You can now use the "Start" button in the browser to launch ROS 2.
pause
