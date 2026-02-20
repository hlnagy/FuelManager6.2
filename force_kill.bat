@echo off
echo ===================================================
echo     FUEL MANAGER - KENYSZERITETT LEALLITAS
echo ===================================================
echo.
echo 1. Minden Python folyamat leallitasa...
taskkill /IM python.exe /F
echo.
echo 2. Bongeszo ablakok tisztitasa (opcionalis)...
taskkill /IM msedge.exe /F /FI "WINDOWTITLE eq Fuel Manager*"
taskkill /IM chrome.exe /F /FI "WINDOWTITLE eq Fuel Manager*"
echo.
echo 3. Kesz. Most mar biztonsagosan ujrainditathatod a 'run_desktop.bat'-tal.
echo.
pause
