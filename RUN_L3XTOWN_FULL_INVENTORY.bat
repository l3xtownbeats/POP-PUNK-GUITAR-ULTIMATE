@echo off
setlocal
title POP PUNK GUITAR ULTIMATE - L3XTOWN FULL INVENTORY

set "PROJECT_ROOT=F:\POP PUNK GUITAR ULTIMATE"
set "LIBRARY_ROOT=%PROJECT_ROOT%\Samples\SourceLibraries\L3XTOWN GUITAR"
set "SAMPLE_MAP=%~dp0L3XTOWN_SAMPLE_MAP.csv"
set "SCRIPT=%TEMP%\BUILD_L3XTOWN_INVENTORY.py"
set "SCRIPT_URL=https://raw.githubusercontent.com/l3xtownbeats/POP-PUNK-GUITAR-ULTIMATE/main/BUILD_L3XTOWN_INVENTORY.py"
set "PYTHON=%LOCALAPPDATA%\PythonPortable\python.exe"

echo.
echo ============================================================
echo   L3XTOWN GUITAR - FULL PATH INVENTORY
echo   READ-ONLY SOURCE SCAN - NO AUDIO OR PLUGIN TESTS
echo ============================================================
echo.

if not exist "%SAMPLE_MAP%" (
  echo ERROR: L3XTOWN_SAMPLE_MAP.csv is missing beside this BAT:
  echo "%SAMPLE_MAP%"
  goto :fail
)
if not exist "%LIBRARY_ROOT%" (
  echo ERROR: Source library folder not found:
  echo "%LIBRARY_ROOT%"
  goto :fail
)

echo Downloading the inventory script automatically...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing -Uri '%SCRIPT_URL%' -OutFile '%SCRIPT%' -ErrorAction Stop } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 (
  echo ERROR: Could not download the inventory script from GitHub.
  goto :fail
)
if not exist "%SCRIPT%" (
  echo ERROR: Download did not create the inventory script.
  goto :fail
)

if not exist "%PYTHON%" (
  where py >nul 2>nul
  if errorlevel 1 (
    echo ERROR: Portable Python and Windows py launcher were not found.
    goto :fail
  )
  set "PYTHON=py"
)

echo Project: "%PROJECT_ROOT%"
echo Source:  "%LIBRARY_ROOT%"
echo.
echo The scan reads WAV headers and recalculates SHA-256.
echo Original source WAV files will not be changed.
echo.
"%PYTHON%" "%SCRIPT%" --root "%LIBRARY_ROOT%" --sample-map "%SAMPLE_MAP%" --out "%~dp0L3XTOWN_FULL_INVENTORY.csv" --report "%~dp0L3XTOWN_INVENTORY_RECONCILIATION.csv"
set "RESULT=%ERRORLEVEL%"

echo.
if "%RESULT%"=="0" (
  echo SUCCESS: Inventory and reconciliation report created.
  echo Upload these two CSV files to the repository root.
) else (
  echo SCAN FINISHED WITH REVIEW REQUIRED. Exit code: %RESULT%
  echo Check missing files, size/hash mismatches and WAV header warnings.
)
echo.
pause
exit /b %RESULT%

:fail
echo.
echo No source files were changed and no scan was started.
echo.
pause
exit /b 2
