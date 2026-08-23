@echo off
setlocal EnableDelayedExpansion
echo =========================================================================
echo   Isaac Sim + ROS 2 WSL2 Unified Launcher (Windows Host)
echo =========================================================================
echo.

REM 1. Detect Isaac Sim installation path
set "ISAAC_SIM_RELEASE_PATH="

if defined ISAAC_SIM_PATH (
    if exist "%ISAAC_SIM_PATH%\setup_ros_env.bat" (
        set "ISAAC_SIM_RELEASE_PATH=%ISAAC_SIM_PATH%"
        goto :path_found
    )
    if exist "%ISAAC_SIM_PATH%\_build\windows-x86_64\release\setup_ros_env.bat" (
        set "ISAAC_SIM_RELEASE_PATH=%ISAAC_SIM_PATH%\_build\windows-x86_64\release"
        goto :path_found
    )
)

if exist "%~dp0_build\windows-x86_64\release\setup_ros_env.bat" (
    set "ISAAC_SIM_RELEASE_PATH=%~dp0_build\windows-x86_64\release"
    goto :path_found
)

if exist "%~dp0..\isaacsim\src\isaacsim\_build\windows-x86_64\release\setup_ros_env.bat" (
    set "ISAAC_SIM_RELEASE_PATH=%~dp0..\isaacsim\src\isaacsim\_build\windows-x86_64\release"
    goto :path_found
)

if exist "D:\git\isaacsim\src\isaacsim\_build\windows-x86_64\release\setup_ros_env.bat" (
    set "ISAAC_SIM_RELEASE_PATH=D:\git\isaacsim\src\isaacsim\_build\windows-x86_64\release"
    goto :path_found
)

if exist "%LOCALAPPDATA%\ov\pkg\isaac-sim-4.5.0\setup_ros_env.bat" (
    set "ISAAC_SIM_RELEASE_PATH=%LOCALAPPDATA%\ov\pkg\isaac-sim-4.5.0"
    goto :path_found
)

if exist "%LOCALAPPDATA%\ov\pkg\isaac-sim-4.2.0\setup_ros_env.bat" (
    set "ISAAC_SIM_RELEASE_PATH=%LOCALAPPDATA%\ov\pkg\isaac-sim-4.2.0"
    goto :path_found
)

:ask_path
echo [ERROR] Could not automatically locate Isaac Sim installation directory.
echo Please set the ISAAC_SIM_PATH environment variable to point to your
echo Isaac Sim installation folder containing 'setup_ros_env.bat' (e.g. D:\isaac-sim).
echo.
set /p USER_INPUT_PATH="Or enter the path manually now: "

if exist "%USER_INPUT_PATH%\setup_ros_env.bat" (
    set "ISAAC_SIM_RELEASE_PATH=%USER_INPUT_PATH%"
    set "ISAAC_SIM_PATH=%USER_INPUT_PATH%"
    goto :path_found
)
if exist "%USER_INPUT_PATH%\_build\windows-x86_64\release\setup_ros_env.bat" (
    set "ISAAC_SIM_RELEASE_PATH=%USER_INPUT_PATH%\_build\windows-x86_64\release"
    set "ISAAC_SIM_PATH=%USER_INPUT_PATH%"
    goto :path_found
)

echo [ERROR] 'setup_ros_env.bat' not found at '%USER_INPUT_PATH%'.
echo.
goto :ask_path

:path_found
echo [INFO] Using Isaac Sim path: %ISAAC_SIM_RELEASE_PATH%
echo.

:menu
echo =========================================================================
echo   Select an Option:
echo =========================================================================
echo   1) Run Three FR3 Robot Tower Demo (Gemini / Rule-Based)
echo   2) Run Industrial Mobile Manipulator Demo
echo   3) Launch Isaac Sim GUI (Empty Scene)
echo   4) Setup WSL2 Firewall Rules (Requires Administrator)
echo   0) Exit
echo =========================================================================
set /p choice="Enter your choice (0-4): "

if "%choice%"=="1" goto run_three_robots
if "%choice%"=="2" goto run_mobile_manip
if "%choice%"=="3" goto run_isaac_gui
if "%choice%"=="4" goto setup_firewall
if "%choice%"=="0" exit /b 0

echo Invalid choice. Try again.
echo.
goto menu


:run_three_robots
echo.
echo [1/2] Configuring Environment and FastDDS...
cd /d "%ISAAC_SIM_RELEASE_PATH%"
call setup_ros_env.bat
if exist "%~dp0setup_fastdds_wsl.py" ( call python.bat "%~dp0setup_fastdds_wsl.py" )
set "FASTDDS_DEFAULT_PROFILES_FILE=%USERPROFILE%\fastdds_profile.xml"
set "RMW_IMPLEMENTATION=rmw_fastrtps_cpp"

echo [2/2] Launching 3x FR3 Robot Tower Simulation...
set "SIM_SCRIPT=%~dp0..\isaacsim_scripts\three_robot_tower.py"
call python.bat "!SIM_SCRIPT!" %*
echo.
echo =========================================================================
echo   Simulation is running! Now open a WSL2 terminal and run:
echo     cd ~/catkin_ws
echo     bash bringup.bash
echo =========================================================================
pause
goto menu


:run_mobile_manip
echo.
echo [1/2] Configuring Environment and FastDDS...
cd /d "%ISAAC_SIM_RELEASE_PATH%"
call setup_ros_env.bat
if exist "%~dp0setup_fastdds_wsl.py" ( call python.bat "%~dp0setup_fastdds_wsl.py" )
set "FASTDDS_DEFAULT_PROFILES_FILE=%USERPROFILE%\fastdds_profile.xml"
set "RMW_IMPLEMENTATION=rmw_fastrtps_cpp"

echo [2/2] Assembling and Launching Industrial Mobile Manipulator...
set "ASSEMBLE_SCRIPT=%~dp0..\isaacsim_scripts\assemble_industrial_mobile_manipulator.py"
set "RUN_SCRIPT=%~dp0..\isaacsim_scripts\run_industrial_mobile_manipulator.py"

set MOBILE_BASE=nova_carter
set ENVIRONMENT=warehouse
call python.bat "!ASSEMBLE_SCRIPT!" --mobile-base !MOBILE_BASE! --environment !ENVIRONMENT!
call python.bat "!RUN_SCRIPT!" --mobile-base !MOBILE_BASE! --environment !ENVIRONMENT! %*
pause
goto menu


:run_isaac_gui
echo.
echo Launching Isaac Sim GUI...
cd /d "%ISAAC_SIM_RELEASE_PATH%"
call isaac-sim.bat
pause
goto menu


:setup_firewall
echo.
echo Running Firewall Configuration Setup...
echo (You must be running this batch file as Administrator)
netsh advfirewall firewall show rule name="WSL2 ROS2 Discovery" >nul 2>nul
if %errorlevel% equ 0 (
    echo [INFO] Firewall rule "WSL2 ROS2 Discovery" already exists. Updating it...
    netsh advfirewall firewall set rule name="WSL2 ROS2 Discovery" new action=allow dir=in profile=any
) else (
    echo [INFO] Creating new firewall rule "WSL2 ROS2 Discovery"...
    netsh advfirewall firewall add rule name="WSL2 ROS2 Discovery" dir=in action=allow protocol=ANY profile=any
)
echo [SUCCESS] Windows Defender Firewall configured for WSL2 FastDDS Discovery.
pause
goto menu
