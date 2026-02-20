# Pre-flight Checklist: Professional Deployment

Use this checklist to verify the improved structure and safety features before building the final EXE.

## 1. Environment Isolation (Clean Install Test)
- [ ] Close the running application.
- [ ] Navigate to `%LocalAppData%` (Win+R -> `%LocalAppData%`).
- [ ] **Rename** the `FuelManager` folder to `FuelManager_Backup`.
- [ ] Start the application (`python app.py`).
- [ ] **Verify**: The app redirects to `/setup` (Welcome Screen).
- [ ] **Verify**: A new `FuelManager` folder is created in AppData.

## 2. Restore Safety Test
- [ ] In the Setup screen, choose "Restaurează Date".
- [ ] Upload an **invalid file** (e.g., a `.txt` file renamed to `.db`).
- [ ] **Verify**: Error message "Fișierul încărcat nu este o bază de date validă".
- [ ] **Verify**: The application stays on the Setup screen.

## 3. Migration Test (Old DB Support)
- [ ] Locate an **old backup** of your database (before the logos update).
- [ ] Upload this old `.db` file in the Restore screen.
- [ ] **Verify**: Success message.
- [ ] **Verify**: You can log in and see user profiles.
- [ ] **Verify**: No "no such column" errors appear in the logs.

## 4. Path Robustness (Code Audit)
- [ ] Check `app.py` for any `open('filename')` calls. They should be `open(os.path.join(DATA_DIR, 'filename'))`.
- [ ] Check `app.py` for template loading. Should use `get_resource_path`.

## 5. EXE Build
- [ ] Run `build.bat`.
- [ ] Ensure `dist/FuelManager.exe` is created.
- [ ] Move `FuelManager.exe` to a completely different folder (e.g., Desktop).
- [ ] Run it.
- [ ] **Verify**: It opens correctly and finds your data from AppData.
