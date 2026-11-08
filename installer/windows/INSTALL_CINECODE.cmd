@echo off
setlocal DisableDelayedExpansion
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
set "CINECODE_EXIT=%ERRORLEVEL%"
if not "%CINECODE_SETUP_NO_PAUSE%"=="1" pause
exit /b %CINECODE_EXIT%
