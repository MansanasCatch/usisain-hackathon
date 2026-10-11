"""Read-only checks for whether the UsisAIn extension is already installed.

Nothing here writes to browser profiles. Any unreadable state returns ``None``
("unknown") so the launcher falls back to asking the user.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from usisain_launcher.browsers import Browser
from usisain_launcher.settings import (
    CHROMIUM_EXTENSION_ID,
    GECKO_EXTENSION_ID,
    SAFARI_EXTENSION_BUNDLE_ID,
)

log = logging.getLogger(__name__)


def user_data_dir(browser: Browser, platform: str | None = None) -> Path | None:
    platform = platform or sys.platform
    if platform == "win32" and browser.win_user_data:
        env_var, rel = browser.win_user_data
        base = os.environ.get(env_var)
        return Path(base) / rel if base else None
    if platform == "darwin" and browser.mac_user_data:
        return Path.home() / "Library" / "Application Support" / browser.mac_user_data
    return None


def chromium_profiles(user_data: Path, is_profile: bool) -> list[Path]:
    if not user_data.is_dir():
        return []
    profiles = [user_data] if is_profile else []
    try:
        for child in user_data.iterdir():
            if child.is_dir() and (child.name == "Default" or child.name.startswith("Profile ")):
                profiles.append(child)
    except OSError as exc:
        log.warning("Cannot list %s: %s", user_data, exc)
    return profiles


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        return json.load(fh)


def chromium_has_extension(profiles: Iterable[Path], ext_id: str) -> bool | None:
    read_any = False
    for profile in profiles:
        for name in ("Secure Preferences", "Preferences"):
            path = profile / name
            if not path.is_file():
                continue
            try:
                data = _read_json(path)
            except (OSError, ValueError) as exc:
                log.debug("Skipping %s: %s", path, exc)
                continue
            read_any = True
            settings = (
                data.get("extensions", {}).get("settings", {}) if isinstance(data, dict) else {}
            )
            if isinstance(settings, dict) and ext_id in settings:
                return True
    return False if read_any else None


def firefox_has_extension(profiles_dir: Path, gecko_id: str) -> bool | None:
    if not profiles_dir.is_dir():
        return None
    read_any = False
    try:
        candidates = [p / "extensions.json" for p in profiles_dir.iterdir() if p.is_dir()]
    except OSError as exc:
        log.warning("Cannot list %s: %s", profiles_dir, exc)
        return None
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = _read_json(path)
        except (OSError, ValueError) as exc:
            log.debug("Skipping %s: %s", path, exc)
            continue
        read_any = True
        addons = data.get("addons", []) if isinstance(data, dict) else []
        for addon in addons if isinstance(addons, list) else []:
            if isinstance(addon, dict) and addon.get("id") == gecko_id:
                return True
    return False if read_any else None


def safari_has_extension(bundle_id: str) -> bool | None:
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.run(
            ["pluginkit", "-m", "-i", bundle_id],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("pluginkit failed: %s", exc)
        return None
    return bundle_id in out


def is_installed(browser: Browser) -> bool | None:
    try:
        if browser.family == "safari":
            return safari_has_extension(SAFARI_EXTENSION_BUNDLE_ID)
        data_dir = user_data_dir(browser)
        if data_dir is None:
            return None
        if browser.family == "firefox":
            return firefox_has_extension(data_dir, GECKO_EXTENSION_ID)
        profiles = chromium_profiles(data_dir, browser.user_data_is_profile)
        return chromium_has_extension(profiles, CHROMIUM_EXTENSION_ID)
    except Exception as exc:  # never let detection crash the launcher
        log.warning("Install check failed for %s: %s", browser.name, exc)
        return None
