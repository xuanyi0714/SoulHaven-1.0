@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title SoulHaven - 一键配置环境
echo.
echo 请保持网络连接，接下来会自动检查 Python、配置虚拟环境并安装依赖。
echo 下载和安装可能需要几分钟，请等待完成提示，不要提前关闭窗口。
echo.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-environment.ps1"
set "SETUP_EXIT=%ERRORLEVEL%"
echo.
if not "%SETUP_EXIT%"=="0" echo 配置未完成，请查看上方错误。修复网络或权限问题后可以重新运行。
echo 现在可以关闭此窗口，也可以按任意键关闭。
pause >nul
exit /b %SETUP_EXIT%
