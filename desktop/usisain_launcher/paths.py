"""Cross-platform filesystem locations used by the launcher."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from usisain_launcher.settings import APP_NAME


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def repo_root() -> Path:
    """Repository root when running from source (desktop/usisain_launcher/paths.py)."""
    return Path(__file__).resolve().parents[2]


def bundle_dir() -> Path:
    """Directory holding bundled resources (PyInstaller's _MEIPASS when frozen)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1] / "build"


def payload_dir() -> Path:
    """Mirrored source tree shipped inside the bundle."""
    return bundle_dir() / "payload"


def assets_dir() -> Path:
    if is_frozen():
        return bundle_dir() / "assets"
    return Path(__file__).resolve().parents[1] / "assets"


def user_data_root() -> Path:
    """Writable per-user folder, e.g. %LOCALAPPDATA%\\UsisAIn or ~/Library/Application Support/UsisAIn."""
    override = os.environ.get("USISAIN_USER_DATA")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_NAME


def runtime_root() -> Path:
    """Where the app code runs from. Source checkouts run straight from the repo."""
    if is_frozen():
        return user_data_root() / "app"
    return repo_root()


def log_dir() -> Path:
    return user_data_root() / "logs"


def config_file() -> Path:
    return user_data_root() / "config.json"


def extension_dir(variant: str) -> Path:
    """Folder of a built extension variant ("chromium", "firefox" or "safari")."""
    if is_frozen():
        return runtime_root() / "extension" / variant
    built = Path(__file__).resolve().parents[1] / "build" / "extension" / variant
    if built.exists() or variant != "chromium":
        return built
    return repo_root() / "client" / "browser-extension"
