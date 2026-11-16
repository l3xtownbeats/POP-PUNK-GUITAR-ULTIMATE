@echo off
setlocal
title L3XTOWN Acoustic Local Preflight

set "PROJECT_ROOT=%~dp0"
set "LIBRARY_ROOT=F:\POP PUNK GUITAR ULTIMATE\Samples\SourceLibraries\L3XTOWN GUITAR"
set "INVENTORY=%PROJECT_ROOT%L3XTOWN_FULL_INVENTORY.csv"
set "SCRIPT=%TEMP%\preflight_l3xtown_acoustic_sources.py"
set "OUTPUT=F:\POP PUNK GUITAR ULTIMATE\Reports\AcousticPreflight"
set "SCRIPT_URL=https://raw.githubusercontent.com/l3xtownbeats/POP-PUNK-GUITAR-ULTIMATE/tool/library-manager-mvp/tools/preflight_l3xtown_acoustic_sources.py"

echo ================================================
echo   L3XTOWN ACOUSTIC LOCAL PREFLIGHT 1.0.2
echo ================================================
echo.
if not exist "%LIBRARY_ROOT%\" (
  echo ERROR: Library folder not found:
  echo "%LIBRARY_ROOT%"
  echo Check that the acoustic library is extracted to the expected location.
  echo.
  pause
  exit /b 1
)
if not exist "%INVENTORY%" (
  echo ERROR: L3XTOWN_FULL_INVENTORY.csv is missing beside this BAT file.
  echo Download the inventory from the project repository and place it here:
  echo "%PROJECT_ROOT%"
  echo.
  pause
  exit /b 1
)

if not exist "%SCRIPT%" (
  echo Python checker is not present locally. Downloading it automatically...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing -Uri '%SCRIPT_URL%' -OutFile '%SCRIPT%'; exit 0 } catch { Write-Host $_; exit 1 }"
  if errorlevel 1 (
    echo.
    echo ERROR: Automatic download failed.
    echo Check your internet connection or download the Python script manually.
    echo.
    echo https://github.com/l3xtownbeats/POP-PUNK-GUITAR-ULTIMATE/blob/tool/library-manager-mvp/tools/preflight_l3xtown_acoustic_sources.py
    pause
    exit /b 1
  )
)
if not exist "%SCRIPT%" (
  echo ERROR: Python script download did not create the expected file:
  echo "%SCRIPT%"
  pause
  exit /b 1
)

where py >nul 2>nul
if not errorlevel 1 (
  py -3 --version
  if errorlevel 1 goto NO_PYTHON
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 goto NO_PYTHON
  python --version
  if errorlevel 1 goto NO_PYTHON
  set "PYTHON_CMD=python"
)

echo.
echo Source WAV files will only be read. No originals will be changed.
echo.
%PYTHON_CMD% "%SCRIPT%" --library-root "%LIBRARY_ROOT%" --inventory "%INVENTORY%" --output-dir "%OUTPUT%" --family acoustic
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

:NO_PYTHON
echo.
echo ERROR: Python 3.10+ was not found. Install Python and enable Add Python to PATH.
pause
exit /b 1
