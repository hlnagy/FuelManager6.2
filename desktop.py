import threading
import sys
import os
import time
import subprocess
import webbrowser
from app import app

def start_flask():
    """Start Flask server in a background thread"""
    # Disable Flask auto-reloader in desktop mode
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

def open_browser_app(url):
    """Open system browser in app mode (no address bar)"""
    try:
        # Try Edge first (pre-installed on Windows)
        # generic 'microsoft-edge:' protocol doesn't support --app flag easily via shell=True
        # We need to find the executable or use 'start msedge --app=...'
        
        # Method 1: Use 'start' command with msedge
        subprocess.Popen(['start', 'msedge', f'--app={url}'], shell=True)
        return True
    except Exception:
        pass
        
    try:
        # Try Chrome
        subprocess.Popen(['start', 'chrome', f'--app={url}'], shell=True)
        return True
    except Exception:
        pass
        
    # Fallback to standard browser window
    print("Could not launch in app mode, falling back to standard browser.")
    webbrowser.open(url)
    return False

def main():
    """Main desktop application entry point"""
    print("Starting Fuel Manager...")
    
    # Start Flask in background thread
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    
    # Wait a moment for Flask to start
    time.sleep(1)
    
    # Launch Browser in App Mode
    url = 'http://127.0.0.1:5000'
    open_browser_app(url)
    
    print(f"\nFuel Manager is running at: {url}")
    print("Close the application window to stop.")
    print("\nPress Ctrl+C to quit...")
    
    # Keep the Flask server running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)

if __name__ == '__main__':
    main()
