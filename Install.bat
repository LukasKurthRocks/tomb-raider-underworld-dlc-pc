@echo off
rem One-click installer of the Tomb Raider: Underworld DLC port (README.md, "Install the DLC").
rem Starts scripts\windows\Install-TruAll.ps1 in Windows PowerShell 5.1; extra arguments are passed on, e.g.
rem   Install.bat -Check        (only list what it would download and do, change nothing)
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Install-TruAll.ps1" %*
set "CODE=%ERRORLEVEL%"
echo.
echo Installer finished with exit code %CODE% (0 = OK). The log file is named above.
pause
exit /b %CODE%
