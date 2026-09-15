@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "LAUNCHER=%SCRIPT_DIR%panel\launcher.py"
set "STATE_DIR=%APPDATA%\codex-wallpaper"
set "PORT=%CODEX_WALLPAPER_PORT%"
if not defined PORT set "PORT=8765"

rem The asar is usually inside a protected install directory. Elevate once
rem so the control panel can replace it without asking users to type paths.
fltmc >nul 2>&1
if errorlevel 1 (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "Start-Process -FilePath '%~f0' -Verb RunAs -WorkingDirectory '%~dp0'"
  exit /b 0
)

if not exist "%STATE_DIR%" mkdir "%STATE_DIR%"

where powershell.exe >nul 2>&1
if errorlevel 1 (
  echo 未找到 Windows PowerShell，无法打开应用选择器和管理员权限。
  pause
  exit /b 1
)

where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%LAUNCHER%" --port %PORT%
  set "LAUNCHER_EXIT=%ERRORLEVEL%"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo 未找到 Python 3。请先安装 Python 3，再重新运行此文件。
    pause
    exit /b 1
  )
  python "%LAUNCHER%" --port %PORT%
  set "LAUNCHER_EXIT=%ERRORLEVEL%"
)

if not "%LAUNCHER_EXIT%"=="0" (
  echo 控制面板启动失败，请查看：
  echo %STATE_DIR%\panel.log
  start "" "%STATE_DIR%\panel.log"
  pause
  exit /b %LAUNCHER_EXIT%
)

exit /b 0
