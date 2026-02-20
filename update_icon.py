# Icon Conversion Script
# Place your PNG icon file named "app_icon.png" in the static folder
# Then run this script to convert it to multi-resolution ICO format

from PIL import Image
import os

png_path = 'static/app_icon.png'
ico_path = 'static/favicon.ico'

if not os.path.exists(png_path):
    print(f"ERROR: {png_path} not found!")
    print("Please save your icon as 'app_icon.png' in the static folder and run this script again.")
    exit(1)

try:
    img = Image.open(png_path)
    
    # Convert to RGBA if needed
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Create multiple sizes for ICO
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = []
    
    for size in sizes:
        resized = img.resize(size, Image.LANCZOS)
        images.append(resized)
    
    # Save as ICO
    images[0].save(ico_path, format='ICO', sizes=[img.size for img in images])
    print(f"Icon successfully converted!")
    print(f"  Input: {png_path}")
    print(f"  Output: {ico_path}")
    print(f"  Sizes: {', '.join([f'{s[0]}x{s[1]}' for s in sizes])}")
    
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
