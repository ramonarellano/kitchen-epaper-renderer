import os
import cairosvg

ICON_DIR = "icons"
PNG_DIR = "icons/png"

os.makedirs(PNG_DIR, exist_ok=True)

def convert_svg(svg_path, png_path):
    try:
        cairosvg.svg2png(url=svg_path, write_to=png_path)
    except ValueError as e:
        if 'size is undefined' in str(e):
            print(f"  [!] No size in {svg_path}, using default 128x128")
            cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=128, output_height=128)
        else:
            print(f"  [!] Failed to convert {svg_path}: {e}")

for filename in os.listdir(ICON_DIR):
    if filename.lower().endswith(".svg"):
        svg_path = os.path.join(ICON_DIR, filename)
        png_path = os.path.join(PNG_DIR, filename[:-4] + ".png")
        print(f"Converting {svg_path} -> {png_path}")
        convert_svg(svg_path, png_path)
