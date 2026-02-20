@echo off
setlocal

:: Get current directory (where the script is running)
set "TARGET_DIR=%~dp0"
:: Remove trailing backslash
set "TARGET_DIR=%TARGET_DIR:~0,-1%"

:: Define the target EXE (must match the folder name usually)
:: We will search for the .exe that starts with FuelManager_v
for %%f in ("%TARGET_DIR%\FuelManager_v*.exe") do set "TARGET_EXE=%%f"

if not defined TARGET_EXE (
    echo [ERROR] Could not find FuelManager executable in this folder.
    pause
    exit /b
)

echo Found executable: %TARGET_EXE%

:: Create VBS script to create shortcut
set "VBS_SCRIPT=%TEMP%\create_shortcut.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%VBS_SCRIPT%"
echo sLinkFile = oWS.SpecialFolders("Desktop") ^& "\Fuel Manager.lnk" >> "%VBS_SCRIPT%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%VBS_SCRIPT%"
echo oLink.TargetPath = "%TARGET_EXE%" >> "%VBS_SCRIPT%"
echo oLink.WorkingDirectory = "%TARGET_DIR%" >> "%VBS_SCRIPT%"
echo oLink.Description = "Fuel Manager Application" >> "%VBS_SCRIPT%"
echo oLink.IconLocation = "%TARGET_EXE%" >> "%VBS_SCRIPT%"
echo oLink.Save >> "%VBS_SCRIPT%"

:: Run VBS script
cscript //nologo "%VBS_SCRIPT%"

:: Clean up
del "%VBS_SCRIPT%"

echo.
echo ========================================================
echo   Shortcut created successfully on your Desktop!
echo   You can now launch the app from there.
echo ========================================================
echo.
pause
