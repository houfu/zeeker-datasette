#!/usr/bin/env python3
# /// script
# dependencies = [
#     "pillow>=10.0.0",
# ]
# ///
"""
Zeeker Image Converter - Convert hero images to WebP with multiple sizes
Run with: uv run scripts/convert_hero_image.py
"""

import os
from pathlib import Path
from PIL import Image, ImageOps
import sys


def convert_hero_image(input_path: str, output_dir: str = "static/images"):
    """Convert hero image to multiple WebP formats with PNG fallbacks."""

    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        return False

    print(f"🖼️  Converting {input_path.name}...")

    # Configuration for different sizes
    sizes = {
        "desktop": {
            "size": (2560, 1440),
            "quality_webp": 85,
            "quality_png": 95,
            "suffix": ""
        },
        "mobile": {
            "size": (1280, 720),
            "quality_webp": 80,
            "quality_png": 90,
            "suffix": "-mobile"
        },
        "tablet": {
            "size": (1920, 1080),
            "quality_webp": 82,
            "quality_png": 92,
            "suffix": "-tablet"
        }
    }

    try:
        with Image.open(input_path) as img:
            print(f"📏 Original size: {img.size}")
            print(f"🎨 Original mode: {img.mode}")

            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                print("🔄 Converting to RGB...")
                # Create white background for transparent images
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])
                    img = background
                else:
                    img = img.convert('RGB')

            base_name = "holographic-building"

            for size_name, config in sizes.items():
                print(f"\n📐 Creating {size_name} version ({config['size'][0]}x{config['size'][1]})...")

                # Resize with high quality
                resized = img.copy()
                resized = ImageOps.fit(
                    resized,
                    config["size"],
                    Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5)
                )

                # Save WebP
                webp_path = output_dir / f"{base_name}{config['suffix']}.webp"
                resized.save(
                    webp_path,
                    'WebP',
                    quality=config['quality_webp'],
                    optimize=True,
                    method=6  # Best compression
                )

                # Save PNG fallback
                png_path = output_dir / f"{base_name}{config['suffix']}.png"
                resized.save(
                    png_path,
                    'PNG',
                    optimize=True,
                    compress_level=6
                )

                # Get file sizes
                webp_size = webp_path.stat().st_size / 1024  # KB
                png_size = png_path.stat().st_size / 1024  # KB
                savings = ((png_size - webp_size) / png_size) * 100

                print(f"  ✅ WebP: {webp_size:.1f}KB")
                print(f"  ✅ PNG:  {png_size:.1f}KB")
                print(f"  💾 Savings: {savings:.1f}%")

        print(f"\n🎉 Conversion complete! Files saved to {output_dir}")
        return True

    except Exception as e:
        print(f"❌ Error converting image: {e}")
        return False


def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 2:
        print("Usage: uv run convert_hero_image.py <input_image_path> [output_directory]")
        print("Example: uv run convert_hero_image.py original_building.png static/images")
        return

    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "static/images"

    success = convert_hero_image(input_path, output_dir)

    if success:
        print("\n📋 Next steps:")
        print("1. Update your CSS to use the new WebP images")
        print("2. Add the WebP detection JavaScript")
        print("3. Test the site with different browsers")
        print("4. Consider using a CDN for even better performance")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()