"""Generate desktop and extension icons (.ico, .icns, .png) from a source image."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def round_corners_and_clean_background(img: Image.Image) -> Image.Image:
    """Ensure RGBA, detect the squircle bounds or apply rounded squircle alpha mask."""
    img = img.convert("RGBA")
    width, height = img.size

    # The AI image has a white border around a squircle centered at ~128..896
    # Let's check bounding box of non-white pixels
    # Any pixel where R > 245 and G > 245 and B > 245 is background border
    bg_threshold = 240
    pixels = img.load()
    if pixels is None:
        return img

    # Find the approximate bounding box of the colored squircle
    left, top, right, bottom = width, height, 0, 0
    for y in range(0, height, 4):
        for x in range(0, width, 4):
            r, g, b, _ = pixels[x, y]  # type: ignore[index]
            if not (r >= bg_threshold and g >= bg_threshold and b >= bg_threshold):
                if x < left:
                    left = x
                if x > right:
                    right = x
                if y < top:
                    top = y
                if y > bottom:
                    bottom = y

    # If squircle detected inside padding, crop and re-center into 1024x1024 with transparent margins
    if 50 < left < 250 and 50 < top < 250 and right > 750 and bottom > 750:
        box = (left, top, right, bottom)
        cropped = img.crop(box)
        # Rescale cropped squircle to fit nicely with modern 10% padding
        target_size = int(1024 * 0.90)
        cropped = cropped.resize((target_size, target_size), Image.Resampling.LANCZOS)

        canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
        offset = ((1024 - target_size) // 2, (1024 - target_size) // 2)

        # Create smooth rounded rectangle mask for the squircle
        mask = Image.new("L", (target_size, target_size), 0)
        draw = ImageDraw.Draw(mask)
        radius = int(target_size * 0.22)  # Standard Apple/macOS squircle curve
        draw.rounded_rectangle([(0, 0), (target_size, target_size)], radius=radius, fill=255)

        canvas.paste(cropped, offset, mask)
        return canvas

    return img


def generate_all_icons(src_path: Path, assets_dir: Path, ext_icons_dir: Path) -> None:
    assets_dir.mkdir(parents=True, exist_ok=True)
    ext_icons_dir.mkdir(parents=True, exist_ok=True)

    orig = Image.open(src_path)
    base = round_corners_and_clean_background(orig)
    if base.size != (1024, 1024):
        base = base.resize((1024, 1024), Image.Resampling.LANCZOS)

    # Save 1024x1024 master
    base.save(assets_dir / "icon-1024.png", format="PNG")

    # Standard icon sizes
    sizes = (16, 24, 32, 48, 64, 128, 256, 512)
    for sz in sizes:
        resized = base.resize((sz, sz), Image.Resampling.LANCZOS)
        resized.save(assets_dir / f"icon-{sz}.png", format="PNG")

    # Extension icons
    for sz in (16, 32, 48, 128):
        resized = base.resize((sz, sz), Image.Resampling.LANCZOS)
        resized.save(ext_icons_dir / f"icon-{sz}.png", format="PNG")

    # Windows .ico (multi-resolution embedded)
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    base.save(assets_dir / "icon.ico", format="ICO", sizes=ico_sizes)

    # macOS .icns
    icns_sizes = [(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)]
    base.save(assets_dir / "icon.icns", format="ICNS", sizes=icns_sizes)

    print(f"Generated icons in {assets_dir} and {ext_icons_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate icon assets")
    parser.add_argument("source", nargs="?", help="Path to 1024x1024 source image")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    assets_dir = root / "desktop" / "assets"
    ext_icons_dir = root / "client" / "browser-extension" / "icons"

    if args.source:
        src = Path(args.source)
    else:
        candidates = list(assets_dir.glob("icon-1024.*"))
        if candidates:
            src = candidates[0]
        else:
            print("Error: No source image provided or found in desktop/assets", file=sys.stderr)
            sys.exit(1)

    generate_all_icons(src, assets_dir, ext_icons_dir)


if __name__ == "__main__":
    main()
