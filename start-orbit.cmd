@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-orbit.ps1" %*
exit /b %ERRORLEVEL%
