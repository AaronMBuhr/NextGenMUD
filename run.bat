@echo off
setlocal

set LOG_WIDTH=80
set LOG_LEVEL=info

if "%~1"=="--log-width" (
    set LOG_WIDTH=%~2
    shift
    shift
)

if "%~1"=="--log-level" (
    set LOG_LEVEL=%~2
    shift
    shift
)

powershell -Command "$env:NEXTGENMUD_LOG_WIDTH=%LOG_WIDTH%; $env:NEXTGENMUD_LOG_LEVEL='%LOG_LEVEL%'; uvicorn NextGenMUD.asgi:application --host 0.0.0.0 --port 8000" 