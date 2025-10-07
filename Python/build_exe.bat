@echo off
rem =============================================
rem  Build the TR3 LAN GUI sample into an exe with PyInstaller
rem =============================================

setlocal
cd /d "%~dp0"

if /I "%1"=="clean" goto :CLEAN

rem --- Verify PyInstaller is available (if not, show guidance)
where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller was not found.
    echo         Please install it with ^"py -3 -m pip install pyinstaller^".
    exit /b 1
)

echo [BUILD] Creating exe with PyInstaller...
pyinstaller ^
    --noconfirm ^
    --clean ^
    --name TR3_LAN_GUI ^
    --windowed ^
    tr3_lan_gui.py

if errorlevel 1 (
    echo [ERROR] Build failed.
    exit /b 1
)

echo.
echo [DONE] You can distribute dist\TR3_LAN_GUI\TR3_LAN_GUI.exe.
echo        Copy the entire dist\ folder for first-time execution.
exit /b 0

:CLEAN
echo [CLEAN] Removing PyInstaller artifacts...
if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__
if exist TR3_LAN_GUI.spec del /f /q TR3_LAN_GUI.spec
echo [CLEAN] Done.
exit /b 0