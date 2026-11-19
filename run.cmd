@echo off
REM SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
REM SPDX-License-Identifier: AGPL-3.0-or-later
REM
REM One-shot launcher for Windows: double-click this file to start the demo.
REM All arguments are forwarded to run.ps1, e.g.  run.cmd -Reset -NoBrowser

setlocal
cd /d "%~dp0"

where pwsh >nul 2>nul
if %ERRORLEVEL%==0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
)

set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
    echo.
    echo [LOI] Khoi chay that bai. Xem log trong thu muc logs.
    echo Nhan phim bat ky de dong cua so...
    pause >nul
)

exit /b %EXITCODE%
