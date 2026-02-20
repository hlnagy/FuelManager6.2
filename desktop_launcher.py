import sys
import os
import ctypes
import threading
import time
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QIcon

# --- WINDOWS TASKBAR FIX ---
# This ensures that Windows recognizes this as a unique app and shows the icon in the taskbar
try:
    myappid = 'mycompany.fuelmanager.v62' # unique string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except:
    pass

# Import the Flask app factory or app object
try:
    from app import app
except ImportError:
    print("Error importing Flask app. Make sure app.py is in the same directory.")
    sys.exit(1)

START_PORT = 5000
START_URL = f"http://127.0.0.1:{START_PORT}"

# --- RESOURCE HELPERS ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class FuelManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fuel Manager v6.2")
        self.resize(1280, 800)
        
        # Set Window Icon if available
        try:
            icon_path = resource_path("static/app_icon.png")
            self.setWindowIcon(QIcon(icon_path)) 
        except:
            pass

        self.browser = QWebEngineView()
        self.setCentralWidget(self.browser)
        
        # Load the local Flask app
        self.browser.setUrl(QUrl(START_URL))

def start_flask():
    # Run Flask without reloader to avoid thread issues
    app.run(host='127.0.0.1', port=START_PORT, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Set Desktop Mode flag to disable heartbeat/auto-shutdown
    import os
    os.environ['DESKTOP_MODE'] = '1'
    
    # 1. Start Flask in a background thread
    server_thread = threading.Thread(target=start_flask)
    server_thread.daemon = True
    server_thread.start()

    # 2. Give Flask a moment to start
    time.sleep(1.0)

    # 3. Start Qt Application
    qt_app = QApplication(sys.argv)
    window = FuelManagerWindow()
    window.showMaximized()

    # 4. Execute App Loop
    sys.exit(qt_app.exec())
