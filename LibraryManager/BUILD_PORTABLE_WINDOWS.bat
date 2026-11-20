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
> "%~dp0dist\POP_PUNK_GUITAR_LIBRARY_MANAGER\portable.mode" echo portable
echo Copy the entire folder to the target Windows PC. User data will be stored in UserData.
endlocal
