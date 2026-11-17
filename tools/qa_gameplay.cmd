@echo off
setlocal
cd /d "%~dp0.."

if "%~1"=="" (
    echo Usage: tools\qa_gameplay.cmd ^<managed-game-copy^> [d3d12^|vulkan^|prebuilt] [timeout-seconds] 1>&2
    exit /b 2
)

set "GAME_ROOT=%~1"
set "BACKEND=%~2"
if not defined BACKEND set "BACKEND=d3d12"
set "TIMEOUT=%~3"
if not defined TIMEOUT set "TIMEOUT=14400"

python "%~dp0qa_storage_guard.py" gameplay --repo-root "%~dp0.." --game-root "%GAME_ROOT%" --backend "%BACKEND%" --timeout-seconds "%TIMEOUT%"
exit /b %ERRORLEVEL%
