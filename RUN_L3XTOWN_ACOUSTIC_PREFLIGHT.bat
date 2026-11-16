@echo off
setlocal
chcp 65001 >nul
title L3XTOWN Acoustic Local Preflight

set "PROJECT_ROOT=%~dp0"
set "LIBRARY_ROOT=F:\POP PUNK GUITAR ULTIMATE\Samples\SourceLibraries\L3XTOWN GUITAR"
set "INVENTORY=%PROJECT_ROOT%L3XTOWN_FULL_INVENTORY.csv"
set "SCRIPT=%PROJECT_ROOT%tools\preflight_l3xtown_acoustic_sources.py"
set "OUTPUT=F:\POP PUNK GUITAR ULTIMATE\Reports\AcousticPreflight"

echo ================================================
echo   L3XTOWN ACOUSTIC LOCAL PREFLIGHT 1.0.0
echo ================================================
echo.
if not exist "%LIBRARY_ROOT%\" (
  echo ERROR: Library folder not found:
  echo "%LIBRARY_ROOT%"
  echo.
  pause
  exit /b 1
)
if not exist "%INVENTORY%" (
  echo ERROR: L3XTOWN_FULL_INVENTORY.csv is missing beside this BAT file.
  echo Download it from the project repository root.
  echo.
  pause
  exit /b 1
)
if not exist "%SCRIPT%" (
  echo ERROR: Preflight Python script is missing:
  echo "%SCRIPT%"
  echo Keep the tools folder beside this BAT file.
  echo.
  pause
  exit /b 1
)

py -3 --version
if errorlevel 1 (
  echo.
  echo Python 3 was not found. Install Python 3.10+ and enable the py launcher.
  pause
  exit /b 1
)

echo.
echo Source WAV files will only be read. No originals will be changed.
echo.
py -3 "%SCRIPT%" --library-root "%LIBRARY_ROOT%" --inventory "%INVENTORY%" --output-dir "%OUTPUT%" --family acoustic
set "RESULT=%ERRORLEVEL%"

echo.
if "%RESULT%"=="0" (
  echo PREFLIGHT PASSED. All selected files passed the checks.
) else if "%RESULT%"=="2" (
  echo PREFLIGHT FINISHED WITH ITEMS REQUIRING REVIEW.
) else (
  echo PREFLIGHT STOPPED WITH AN ERROR.
)
echo.
echo Reports folder:
echo "%OUTPUT%"
echo.
pause
exit /b %RESULT%
