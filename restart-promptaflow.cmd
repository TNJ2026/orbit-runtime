@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart-promptaflow.ps1" %*
exit /b %ERRORLEVEL%
