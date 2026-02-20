@echo off
echo ===========================================
echo   Fuel Manager - Building EXE Distribution
echo ===========================================
echo.

:: Ask for Version
set /p APP_VERSION="Enter Version Number (e.g. 6.2): "
if "%APP_VERSION%"=="" set APP_VERSION=6.2

echo Building Version: v%APP_VERSION%
echo.

:: Check for Python Availability
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found!
    echo.
    echo Please install Python from python.org and ensure you check "Add Python to PATH".
    echo.
    pause
    exit /b
)

:: Ensure PyInstaller is installed (using python -m pip)
echo [1/3] Checking dependencies...
python -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller
)

:: Clean previous builds
echo [2/3] Cleaning up old builds...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q FuelManager.spec 2>nul

:: Build the EXE (using python -m PyInstaller)
echo [3/3] Packaging Application (Qt Desktop Mode)...
echo This takes a moment...

:: Note: We use desktop_launcher.py as entry point
python -m PyInstaller --noconfirm --onedir --windowed ^
    --name "FuelManager_v%APP_VERSION%" ^
    --icon "static/app_icon.png" ^
    --hidden-import "pandas" ^
    --hidden-import "openpyxl" ^
    --hidden-import "pystray" ^
    --hidden-import "PIL" ^
    --hidden-import "sqlite3" ^
    --hidden-import "PySide6" ^
    --hidden-import "xhtml2pdf" ^
    --hidden-import "fpdf" ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data "setup_shortcut.bat;." ^
    --add-data "INSTALL.txt;." ^
    --add-data "arial_report.ttf;." ^
    desktop_launcher.py

echo.
if exist "dist\FuelManager_v%APP_VERSION%\FuelManager_v%APP_VERSION%.exe" (
    echo ===========================================
    echo   BUILD SUCCESSFUL! 
    echo   Your app folder is ready in: dist\FuelManager_v%APP_VERSION%\
    echo ===========================================
) else (
    echo ===========================================
    echo   BUILD FAILED. Check errors above.
    echo ===========================================
)
pause
