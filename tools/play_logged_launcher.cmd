@echo off
rem ===========================================================================
rem Play the INSTALLED Fable II (Project Sparrow launcher) with performance
rem logging, for analysing hitches afterwards. Same logging as
rem play_logged.cmd, which runs the local dev build instead.
rem
rem   - FABLE2_FPS_METER=1 writes one line per frame to fps_meter.log.
rem   - REX_D3D12_LOG_PIPELINE_TIMING=true (the SDK cvar as an environment
rem     variable) logs every shader translation, pipeline build and draw wait
rem     of 1 ms or more to the game log.
rem
rem The launcher starts the game with the environment it inherited, and with
rem the data folder as its working directory, so both logs land there:
rem   %LOCALAPPDATA%\ProjectSparrow-Data\logs\fable_2_NNN.log
rem   %LOCALAPPDATA%\ProjectSparrow-Data\play_logs\fps_meter_<date-time>.log
rem (fps_meter.log is recreated on every launch, so this moves it once the
rem game closes.) Uses the launcher's default data folder.
rem ===========================================================================
setlocal
set "LAUNCHER=%LOCALAPPDATA%\ProjectSparrow\current\Fable2Launcher.exe"
set "DATA=%LOCALAPPDATA%\ProjectSparrow-Data"
if not exist "%LAUNCHER%" (
  echo Project Sparrow is not installed: "%LAUNCHER%" not found.
  pause
  exit /b 1
)
if not exist "%DATA%\play_logs" mkdir "%DATA%\play_logs"

set FABLE2_FPS_METER=1
set REX_D3D12_LOG_PIPELINE_TIMING=true
rem Started directly (not through the "Project Sparrow.exe" stub) so the
rem environment is certain to reach the launcher and the game.
start "" "%LAUNCHER%"

rem The launcher closes itself once it starts the game: wait for the game to
rem appear (for as long as the launcher is open), then for it to exit.
powershell -NoProfile -Command ^
  "while (-not (Get-Process fable_2 -ErrorAction SilentlyContinue)) {" ^
  "  if (-not (Get-Process Fable2Launcher -ErrorAction SilentlyContinue)) { Start-Sleep 3; if (-not (Get-Process fable_2 -ErrorAction SilentlyContinue)) { exit 1 } }" ^
  "  Start-Sleep 1 }" ^
  "Wait-Process fable_2"
if errorlevel 1 exit /b 0

for /f %%t in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "STAMP=%%t"
if exist "%DATA%\fps_meter.log" move /y "%DATA%\fps_meter.log" "%DATA%\play_logs\fps_meter_%STAMP%.log" >nul
