@echo off
setlocal enabledelayedexpansion

echo === ADBTool Launcher ===
echo.

:: Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    where py >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo Python is not installed. Installing Python...
        echo.
        
        :: Create temp directory for Python installer
        mkdir "%TEMP%\adbtool_setup" 2>nul
        
        echo Downloading Python installer...
        powershell -Command "& {Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.13.3/python-3.13.3-amd64.exe' -OutFile '%TEMP%\adbtool_setup\python_installer.exe'}"
        
        if not exist "%TEMP%\adbtool_setup\python_installer.exe" (
            echo Failed to download Python installer.
            echo Please install Python manually from https://www.python.org/downloads/
            echo Then run this launcher again.
            pause
            exit /b 1
        )
        
        echo Installing Python...
        echo This may take a few minutes. Please wait...
        "%TEMP%\adbtool_setup\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1
        
        if %ERRORLEVEL% neq 0 (
            echo Python installation failed.
            echo Please install Python manually from https://www.python.org/downloads/
            echo Then run this launcher again.
            pause
            exit /b 1
        )
        
        :: Clean up
        rmdir /S /Q "%TEMP%\adbtool_setup" 2>nul
        
        echo Python installed successfully.
        echo.
    ) else (
        set PYTHON_CMD=py
    )
) else (
    set PYTHON_CMD=python
)

:: If PYTHON_CMD wasn't set above, try again now that it's installed
if not defined PYTHON_CMD (
    where python >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        where py >nul 2>nul
        if %ERRORLEVEL% neq 0 (
            echo Python installation was completed but Python command not found.
            echo Please restart your computer and try again.
            pause
            exit /b 1
        ) else (
            set PYTHON_CMD=py
        )
    ) else (
        set PYTHON_CMD=python
    )
)

:: Ensure devices directory exists
if not exist "./config/devices" (
    mkdir "./config/devices"
)

:: Ensure commands.conf exists
if not exist "./config/commands.conf" (
    echo Get device info > "./config/commands.conf"
    echo shell getprop ro.product.model >> "./config/commands.conf"
    echo shell getprop ro.product.manufacturer >> "./config/commands.conf"
    echo.>> "./config/commands.conf"
    echo Android Version >> "./config/commands.conf"
    echo shell getprop ro.build.version.release >> "./config/commands.conf"
    echo.>> "./config/commands.conf"
    echo System >> "./config/commands.conf"
    echo shell settings list system >> "./config/commands.conf"
    echo.>> "./config/commands.conf"
    echo Battery >> "./config/commands.conf"
    echo shell dumpsys battery >> "./config/commands.conf"
    echo.>> "./config/commands.conf"
    echo Disable Quest Proximity Sensor >> "./config/commands.conf"
    echo shell am broadcast -a com.oculus.vrpowermanager.prox_close >> "./config/commands.conf"
    echo.>> "./config/commands.conf"
    echo Enable Quest Proximity Sensor >> "./config/commands.conf"
    echo shell am broadcast -a com.oculus.vrpowermanager.automation_disable >> "./config/commands.conf"
    echo.>> "./config/commands.conf"
    echo View installed packages >> "./config/commands.conf"
    echo shell pm list packages >> "./config/commands.conf"
    echo.>> "./config/commands.conf"
    echo Reboot device >> "./config/commands.conf"
    echo reboot >> "./config/commands.conf"
)

:: Check if adb.exe exists
if not exist "./bin/adb.exe" (
    echo ERROR: adb.exe not found in the current directory.
    echo Please make sure adb.exe is in the same directory as this launcher.
    pause
    exit /b 1
)

:: Launch ADBTool
echo Starting ADBTool...
%PYTHON_CMD% ./bin/ADBCommandTool.py

:: If ADBTool exits with an error, pause to show the error message
if %ERRORLEVEL% neq 0 (
    echo.
    echo ADBTool exited with an error.
    pause
)

exit /b
