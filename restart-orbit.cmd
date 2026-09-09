@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart-orbit.ps1" %*
exit /b %ERRORLEVEL%
