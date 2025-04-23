#!/usr/bin/env python3
"""
Icon Generator for Repolizer PWA
--------------------------------
This script generates all the necessary icon sizes for PWA from a source image.
It requires Pillow to be installed: pip install Pillow
"""

import os
from PIL import Image

# Ensure the static/icons directory exists
icons_dir = os.path.join('static', 'icons')
os.makedirs(icons_dir, exist_ok=True)

# Source icon path (adjust as needed)
source_icon = os.path.join(icons_dir, 'icon-512x512.png')

# Check if source icon exists
if not os.path.exists(source_icon):
    print(f"Source icon not found at {source_icon}")
    print("Please place a 512x512 PNG icon at this location and try again.")
    exit(1)

# Define icon sizes to generate
icon_sizes = [
    ('favicon-16x16.png', 16),
    ('favicon-32x32.png', 32),
    ('favicon-48x48.png', 48),
    ('apple-touch-icon.png', 180),
    ('icon-72x72.png', 72),
    ('icon-96x96.png', 96),
    ('icon-128x128.png', 128),
    ('icon-144x144.png', 144),
    ('icon-152x152.png', 152),
    ('icon-192x192.png', 192),
    ('icon-384x384.png', 384),
    ('icon-512x512.png', 512),
    ('maskable-icon.png', 512),  # For maskable icons (with padding)
]

# Load the source image
source_img = Image.open(source_icon)

# Generate icons
print("Generating PWA icons...")
for icon_name, size in icon_sizes:
    output_path = os.path.join(icons_dir, icon_name)
    
    # Create a copy of the image for resizing
    img = source_img.copy()
    
    # Special case for maskable icon - add padding (safe zone is 40% of width)
    if icon_name == 'maskable-icon.png':
        # Create a new image with padding
        safe_zone_ratio = 0.8  # 80% of the image will be visible
        canvas_size = size
        visible_size = int(size * safe_zone_ratio)
        padding = (canvas_size - visible_size) // 2
        
        # Create a new image with the background color
        background_color = (0, 219, 222)  # #00DBDE - match brand color
        padded_img = Image.new('RGBA', (canvas_size, canvas_size), background_color)
        
        # Resize the original image to fit within the safe zone
        img = img.resize((visible_size, visible_size), Image.LANCZOS)
        
        # Paste the resized image onto the padded canvas
        padded_img.paste(img, (padding, padding), img if img.mode == 'RGBA' else None)
        
        # Use the padded image for saving
        padded_img.save(output_path)
        print(f"Created {icon_name} ({size}x{size})")
        continue
    
    # Regular icon resizing
    img = img.resize((size, size), Image.LANCZOS)
    img.save(output_path)
    print(f"Created {icon_name} ({size}x{size})")

print("PWA icon generation complete!")
