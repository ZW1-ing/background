@echo off
setlocal

call "%~dp0codex-wallpaper\open-control-panel.bat" %*
exit /b %ERRORLEVEL%
