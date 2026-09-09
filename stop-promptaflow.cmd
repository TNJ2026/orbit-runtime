@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-promptaflow.ps1" %*
exit /b %ERRORLEVEL%
