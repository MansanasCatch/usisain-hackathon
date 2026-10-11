"""Build and validate cross-browser extension bundles (Chromium and Firefox)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

desktop_dir = str(Path(__file__).resolve().parent.parent)
if desktop_dir not in sys.path:
    sys.path.insert(0, desktop_dir)

from usisain_launcher.settings import GECKO_EXTENSION_ID


def validate_manifest(manifest: dict[str, Any], ext_dir: Path, variant: str) -> list[str]:
    """Validate manifest fields and ensure all referenced files exist."""
    errors: list[str] = []

    if manifest.get("manifest_version") != 3:
        errors.append(f"Expected manifest_version 3, got {manifest.get('manifest_version')}")

    if not manifest.get("name"):
        errors.append("Manifest missing 'name'")

    if not manifest.get("version"):
        errors.append("Manifest missing 'version'")

    # Validate icons exist
    icons = manifest.get("icons", {})
    if isinstance(icons, dict):
        for size, path_str in icons.items():
            if not (ext_dir / path_str).is_file():
                errors.append(f"Missing icon {size}: {path_str}")

    # Validate action popup and icon
    action = manifest.get("action", {})
    if isinstance(action, dict):
        popup = action.get("default_popup")
        if popup and not (ext_dir / popup).is_file():
            errors.append(f"Missing default_popup: {popup}")
        act_icons = action.get("default_icon", {})
        if isinstance(act_icons, dict):
            for size, path_str in act_icons.items():
                if not (ext_dir / path_str).is_file():
                    errors.append(f"Missing action icon {size}: {path_str}")

    # Validate background scripts
    bg = manifest.get("background", {})
    if isinstance(bg, dict):
        if "service_worker" in bg:
            sw = bg["service_worker"]
            if not (ext_dir / sw).is_file():
                errors.append(f"Missing background service_worker: {sw}")
        if "scripts" in bg:
            for s in bg["scripts"]:
                if not (ext_dir / s).is_file():
                    errors.append(f"Missing background script: {s}")

    # Validate content scripts
    for cs in manifest.get("content_scripts", []):
        if isinstance(cs, dict):
            for js in cs.get("js", []):
                if not (ext_dir / js).is_file():
                    errors.append(f"Missing content_script file: {js}")

    # Variant specific checks
    if variant == "firefox":
        gecko = (
            manifest.get("browser_specific_settings", {}).get("gecko", {})
            if isinstance(manifest.get("browser_specific_settings"), dict)
            else {}
        )
        if not gecko.get("id"):
            errors.append("Firefox manifest missing browser_specific_settings.gecko.id")
        if "key" in manifest:
            errors.append("Firefox manifest should not include 'key' field")

    return errors


def build_extensions(src_dir: Path, out_dir: Path) -> bool:
    """Build chromium and firefox extensions in out_dir."""
    print(f"Building browser extensions from {src_dir} to {out_dir}...")
    chromium_dir = out_dir / "chromium"
    firefox_dir = out_dir / "firefox"

    for d in (chromium_dir, firefox_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    # Base manifest
    base_manifest_path = src_dir / "manifest.json"
    if not base_manifest_path.is_file():
        print(f"Error: {base_manifest_path} not found", file=sys.stderr)
        return False

    with base_manifest_path.open("r", encoding="utf-8") as f:
        base_manifest = json.load(f)

    # 1. Chromium Build
    # Copy all files from src_dir
    shutil.copytree(src_dir, chromium_dir, dirs_exist_ok=True)
    # Ensure compat.js is present
    if not (chromium_dir / "compat.js").is_file():
        print("Error: compat.js missing in chromium bundle", file=sys.stderr)
        return False

    chromium_errors = validate_manifest(base_manifest, chromium_dir, "chromium")
    if chromium_errors:
        print(f"Chromium manifest validation failed: {chromium_errors}", file=sys.stderr)
        return False

    # 2. Firefox Build
    shutil.copytree(src_dir, firefox_dir, dirs_exist_ok=True)
    firefox_manifest = dict(base_manifest)

    # Firefox uses background.scripts instead of service_worker for better stability in MV3
    firefox_manifest["background"] = {"scripts": ["compat.js", "background.js"]}

    # Remove chromium-specific key from Firefox manifest
    firefox_manifest.pop("key", None)

    # Add browser_specific_settings for Gecko
    firefox_manifest["browser_specific_settings"] = {
        "gecko": {
            "id": GECKO_EXTENSION_ID,
            "strict_min_version": "109.0",
        }
    }

    firefox_manifest_path = firefox_dir / "manifest.json"
    with firefox_manifest_path.open("w", encoding="utf-8") as f:
        json.dump(firefox_manifest, f, indent=2)

    firefox_errors = validate_manifest(firefox_manifest, firefox_dir, "firefox")
    if firefox_errors:
        print(f"Firefox manifest validation failed: {firefox_errors}", file=sys.stderr)
        return False

    print("Successfully built and validated Chromium and Firefox extensions.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and validate extensions")
    parser.add_argument("--src", help="Source extension directory")
    parser.add_argument("--out", help="Output directory")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    src = Path(args.src) if args.src else repo_root / "client" / "browser-extension"
    out = Path(args.out) if args.out else repo_root / "desktop" / "build" / "extension"

    success = build_extensions(src, out)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
