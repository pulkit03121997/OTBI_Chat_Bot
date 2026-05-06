@echo off
title Orbrick SQL Automation
color 0A
echo.
echo  ==========================================
echo   Orbrick SQL Automation
echo   Oracle Fusion BIP SQL Generator
echo   orbrick.com
echo  ==========================================
echo.
echo  Starting application...
echo.

cd /d "%~dp0"
python app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  ERROR: Could not start the application.
    echo  Make sure Python 3.8+ is installed.
    echo  Download from: https://www.python.org/downloads/
    echo.
    pause
)
