@echo off
setlocal

set LOG_WIDTH=80
set LOG_LEVEL=1

if "%~1"=="--log-width" (
    set LOG_WIDTH=%~2
    shift
    shift
)

if "%~1"=="--log-level" (
    if "%~2"=="debug" set LOG_LEVEL=1
    if "%~2"=="debug2" set LOG_LEVEL=2
    if "%~2"=="debug3" set LOG_LEVEL=3
    shift
    shift
)

powershell -Command "$env:NEXTGENMUD_LOG_WIDTH=%LOG_WIDTH%; $env:NEXTGENMUD_LOG_LEVEL=%LOG_LEVEL%; uvicorn NextGenMUD.asgi:application --host 0.0.0.0 --port 8000" 