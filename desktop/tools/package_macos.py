"""Package UsisAIn macOS Universal Distribution zip.
Creates desktop/dist/UsisAIn-macos-universal.zip containing the entire application
distribution with macOS launchers, extension loaders, and build scripts.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DIST_DIR = REPO_ROOT / "desktop" / "dist"
DIST_DIR.mkdir(parents=True, exist_ok=True)
ZIP_OUT = DIST_DIR / "UsisAIn-macos-universal.zip"

EXCLUDE_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    "node_modules",
}

EXCLUDE_EXTS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".tmp",
    ".log",
    ".msi",
    ".exe",
}

EXCLUDE_EXACT = {
    "app.db",
    "app.db-journal",
    "app.db-wal",
    "app.db-shm",
    ".env",
}


def should_include(rel_path: Path) -> bool:
    parts = rel_path.parts
    for part in parts:
        if part in EXCLUDE_DIRS:
            return False
    if rel_path.name in EXCLUDE_EXACT:
        return False
    if rel_path.suffix.lower() in EXCLUDE_EXTS:
        return False
    # Don't include desktop/dist inside the zip
    if len(parts) >= 2 and parts[0] == "desktop" and parts[1] == "dist":
        return False
    if len(parts) >= 2 and parts[0] == "desktop" and parts[1] == "build":
        return False
    return True


def package_macos_zip():
    print(f"Creating {ZIP_OUT}...")
    file_count = 0
    with zipfile.ZipFile(ZIP_OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(REPO_ROOT):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file in files:
                abs_path = Path(root) / file
                rel_path = abs_path.relative_to(REPO_ROOT)
                if should_include(rel_path):
                    # Ensure unix permissions for scripts
                    zinfo = zipfile.ZipInfo.from_file(abs_path, arcname=str(rel_path).replace("\\", "/"))
                    if rel_path.suffix == ".sh" or rel_path.name == "run.py":
                        zinfo.external_attr = 0o755 << 16  # rwxr-xr-x
                    zf.writestr(zinfo, abs_path.read_bytes())
                    file_count += 1

    size_mb = ZIP_OUT.stat().st_size / (1024 * 1024)
    print(f"[OK] Created {ZIP_OUT} ({size_mb:.2f} MB, {file_count} files)")


if __name__ == "__main__":
    package_macos_zip()
