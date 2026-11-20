@echo off
setlocal
cd /d "%~dp0"
py -3.11 -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
py -3.11 -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1
py -3.11 -m PyInstaller --noconfirm --clean --windowed --onedir --name POP_PUNK_GUITAR_LIBRARY_MANAGER --paths . --add-data "ppgu_skin;ppgu_skin" --add-data "PORTABLE_USER_GUIDE_RU.md;." --collect-all soundfile --collect-all _soundfile_data manager_gui.py
if errorlevel 1 exit /b 1
echo.
echo Build completed: %~dp0dist\POP_PUNK_GUITAR_LIBRARY_MANAGER
if exist "dist\POP_PUNK_GUITAR_LIBRARY_MANAGER\UserData" rmdir /s /q "dist\POP_PUNK_GUITAR_LIBRARY_MANAGER\UserData"
powershell -NoProfile -Command "[guid]::NewGuid().ToString('N') | Set-Content -NoNewline 'dist\POP_PUNK_GUITAR_LIBRARY_MANAGER\portable.mode'"
powershell -NoProfile -Command "if (Test-Path 'dist\POP_PUNK_GUITAR_LIBRARY_MANAGER-windows-x64.zip') { Remove-Item 'dist\POP_PUNK_GUITAR_LIBRARY_MANAGER-windows-x64.zip' -Force }; Compress-Archive -Path 'dist\POP_PUNK_GUITAR_LIBRARY_MANAGER' -DestinationPath 'dist\POP_PUNK_GUITAR_LIBRARY_MANAGER-windows-x64.zip'"
if errorlevel 1 exit /b 1
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
  "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%~dp0POP_PUNK_GUITAR_LIBRARY_MANAGER.iss"
  if errorlevel 1 exit /b 1
) else (
  echo Inno Setup not found. Portable ZIP is ready; install Inno Setup to build installer EXE.
)
echo Portable ZIP: %~dp0dist\POP_PUNK_GUITAR_LIBRARY_MANAGER-windows-x64.zip
echo User data will be stored in UserData for portable mode.
endlocal
