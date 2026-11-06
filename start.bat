@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if "%~1"=="--wait-for-server" goto wait_for_server
title SoulHaven
color 07

set "PYTHON=%~dp0backend\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Project Python was not found:
    echo "%PYTHON%"
    echo 请先运行项目根目录的“^(小白可选^)一键配置环境.bat”。
    pause
    exit /b 1
)

echo Starting SoulHaven...
echo Python: "%PYTHON%"
echo Website: http://127.0.0.1:5000
echo Press Ctrl+C to stop the server.
echo.

rem Start a second ordinary CMD that waits until Flask serves the homepage.
start "" /b "%~f0" --wait-for-server

rem Run Python directly in this CMD console, not through file associations.
"%PYTHON%" -m backend.app

echo.
echo SoulHaven stopped.
pause
endlocal
exit /b

:wait_for_server
set "URL=http://127.0.0.1:5000/"
set /a ATTEMPTS=0
:check_server
set /a ATTEMPTS+=1
curl.exe --silent --show-error --fail --max-time 2 "%URL%" >nul 2>nul
if not errorlevel 1 (
    start "" "%URL%"
    exit /b 0
)
if %ATTEMPTS% GEQ 120 exit /b 1
timeout /t 1 /nobreak >nul
goto check_server
