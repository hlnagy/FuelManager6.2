"""
System Tray Icon Manager for Fuel Manager
Provides visual indicator and Exit button in system tray
"""
import pystray
from PIL import Image, ImageDraw
import threading
import urllib.request
import sys

class SystemTrayManager:
    def __init__(self, port=5000):
        self.port = port
        self.icon = None
        self.running = False
        
    def create_icon_image(self):
        """Create a simple tray icon (blue droplet)"""
        # Create 64x64 image with alpha channel
        width = 64
        height = 64
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw a water droplet shape (simplified)
        # Droplet body (ellipse)
        draw.ellipse([16, 24, 48, 56], fill=(33, 150, 243, 255))
        # Droplet top (triangle-ish shape)
        draw.polygon([(32, 8), (16, 24), (48, 24)], fill=(33, 150, 243, 255))
        
        return image
    
    def on_exit(self, icon, item):
        """Handle Exit menu click"""
        print("Shutting down Fuel Manager...")
        
        # Call shutdown endpoint using urllib (built-in, no external dependency)
        try:
            req = urllib.request.Request(
                f'http://localhost:{self.port}/api/shutdown',
                data=b'',
                method='POST'
            )
            urllib.request.urlopen(req, timeout=2)
        except:
            pass  # Server might already be down
        
        # Stop the tray icon
        self.running = False
        icon.stop()
        
    def on_open(self, icon, item):
        """Handle Open menu click"""
        import webbrowser
        webbrowser.open(f'http://localhost:{self.port}/')
    
    def setup(self):
        """Setup and return tray icon (doesn't start it yet)"""
        image = self.create_icon_image()
        
        menu = pystray.Menu(
            pystray.MenuItem('Open Fuel Manager', self.on_open, default=True),
            pystray.MenuItem('Exit', self.on_exit)
        )
        
        self.icon = pystray.Icon(
            'FuelManager',
            image,
            'Fuel Manager',
            menu
        )
        
        return self.icon
    
    def run_in_background(self):
        """Run the tray icon in a background thread"""
        if not self.icon:
            self.setup()
        
        self.running = True
        
        def run_icon():
            try:
                self.icon.run()
            except:
                pass
        
        thread = threading.Thread(target=run_icon, daemon=True)
        thread.start()
        return thread
