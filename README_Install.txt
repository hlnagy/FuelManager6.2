FUEL MANAGER - Installation Instructions
==========================================

VERSION: 2.0.0
DATE: February 2026

WHAT'S NEW IN VERSION 2.0
--------------------------
✓ Empty database on fresh install - Add your own companies
✓ Fixed UNDO/REDO functionality with full state tracking
✓ Professional Windows installer
✓ Start Menu integration
✓ Desktop shortcut (optional)
✓ Proper uninstaller
✓ Modern fuel pump icon

INSTALLATION REQUIREMENTS
--------------------------
- Windows 10 or Windows 11 (64-bit)
- 100 MB free disk space
- Administrator privileges (for installation)
- Chrome or Microsoft Edge (recommended for app mode)

HOW TO INSTALL
--------------
1. Double-click "FuelManager_v2.0.0_Setup.exe"
2. Follow the installation wizard
3. Choose installation location (default: C:\Program Files\Fuel Manager)
4. Select if you want a desktop shortcut
5. Click "Install"

FIRST RUN
---------
When you first launch Fuel Manager:
1. The application opens in its own window (app mode)
2. The database is completely EMPTY
3. Go to "Admin" → "Gestiune Firme" to add your first company
4. Add vehicles and start tracking fuel consumption

USAGE
-----
- Dashboard: Overview of all fuel stocks
- Stoc: Detailed stock information per company
- Importare CSV: Import transaction data from CSV files
- Rapoarte: Generate PDF consumption reports  
- Admin: Manage companies and vehicles

UNDO/REDO FUNCTIONALITY
-----------------------
The UNDO/REDO buttons on the Stock Details page now work correctly:
- UNDO: Reverses the last stock operation or transaction
- REDO: Re-applies a previously undone action
- Full state tracking for CREATE, UPDATE, and DELETE operations

DATA LOCATION
-------------
All data is stored in:
C:\Program Files\Fuel Manager\fuel_manager_v2.db

IMPORTANT: Back up this file regularly!

UNINSTALLATION
--------------
Option 1: Start Menu → Fuel Manager → Uninstall Fuel Manager
Option 2: Settings → Apps → Fuel Manager → Uninstall
Option 3: Control Panel → Programs and Features → Fuel Manager → Uninstall

The uninstaller will remove:
- Application files
- Database file
- Start Menu shortcuts
- Desktop shortcut (if created)

NOTES
-----
- The application runs completely offline
- No internet connection required
- Port 5000 is used for local communication
- If the app window doesn't open automatically, a browser window will open instead

SUPPORT
-------
For issues or questions, contact your system administrator.

================================================================================
© 2026 Transgat Group. All rights reserved.
