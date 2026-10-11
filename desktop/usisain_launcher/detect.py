"""Detect running browsers, the system default browser, and browser executables."""

from __future__ import annotations

import csv
import io
import logging
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Any

from usisain_launcher.browsers import ALL_BROWSERS, Browser, supported_on

log = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000
LAUNCH_SERVICES_PLIST = (
    Path("Library")
    / "Preferences"
    / "com.apple.LaunchServices"
    / "com.apple.launchservices.secure.plist"
)


def _run(cmd: list[str], timeout: float = 10.0) -> str:
    kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = CREATE_NO_WINDOW
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        encoding="utf-8",
        errors="replace",
        **kwargs,
    )
    return result.stdout


# --------------------------------------------------------------------------- parsing


def parse_tasklist(output: str, platform: str = "win32") -> list[Browser]:
    """Parse `tasklist /FO CSV /NH` output into running browsers (catalogue order)."""
    images: set[str] = set()
    for row in csv.reader(io.StringIO(output)):
        if row:
            images.add(row[0].strip().lower())
    return [b for b in supported_on(platform) if b.win_process and b.win_process in images]


def parse_ps(output: str) -> list[Browser]:
    """Parse `ps -axo comm=` output (macOS) into running browsers."""
    found: list[Browser] = []
    for browser in ALL_BROWSERS:
        marker = f"/{browser.mac_app}/Contents/MacOS/"
        if browser.mac_app and any(marker in line for line in output.splitlines()):
            found.append(browser)
    return found


def browser_from_progid(progid: str) -> Browser | None:
    for browser in ALL_BROWSERS:
        if any(progid.startswith(p) for p in browser.win_progid_prefixes):
            return browser
    return None


def default_from_launchservices(data: dict[str, Any]) -> Browser | None:
    """Pick the http/https handler from the LaunchServices secure plist."""
    handlers = data.get("LSHandlers", [])
    if not isinstance(handlers, list):
        return None
    for scheme in ("http", "https"):
        for entry in handlers:
            if not isinstance(entry, dict) or entry.get("LSHandlerURLScheme") != scheme:
                continue
            bundle = str(entry.get("LSHandlerRoleAll", "")).lower()
            for browser in ALL_BROWSERS:
                if browser.mac_bundle_id and browser.mac_bundle_id.lower() == bundle:
                    return browser
    return None


# --------------------------------------------------------------------------- live detection


def running_browsers() -> list[Browser]:
    try:
        if sys.platform == "win32":
            return parse_tasklist(_run(["tasklist", "/FO", "CSV", "/NH"]))
        if sys.platform == "darwin":
            return parse_ps(_run(["ps", "-axo", "comm="]))
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("Could not list running processes: %s", exc)
    return []


def default_browser() -> Browser | None:
    try:
        if sys.platform == "win32":
            return _windows_default_browser()
        if sys.platform == "darwin":
            return _mac_default_browser()
    except (OSError, ValueError, plistlib.InvalidFileException) as exc:
        log.warning("Could not read the default browser: %s", exc)
    return None


def _windows_default_browser() -> Browser | None:
    import winreg

    for scheme in ("http", "https"):
        key_path = (
            "Software\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\"
            f"{scheme}\\UserChoice"
        )
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                progid, _ = winreg.QueryValueEx(key, "ProgId")
        except OSError:
            continue
        browser = browser_from_progid(str(progid))
        if browser:
            return browser
        log.info("Default browser ProgId %r is not a supported browser", progid)
    return None


def _mac_default_browser() -> Browser | None:
    from usisain_launcher.browsers import SAFARI

    plist = Path.home() / LAUNCH_SERVICES_PLIST
    if not plist.exists():
        return SAFARI  # macOS ships with Safari as the default handler.
    with plist.open("rb") as fh:
        data = plistlib.load(fh)
    return default_from_launchservices(data) or SAFARI


def find_executable(browser: Browser) -> Path | None:
    if sys.platform == "win32":
        return _windows_executable(browser)
    if sys.platform == "darwin":
        for apps in (Path("/Applications"), Path.home() / "Applications"):
            binary = apps / browser.mac_app / "Contents" / "MacOS" / browser.mac_binary
            if browser.mac_app and binary.exists():
                return binary
    return None


def mac_app_path(browser: Browser) -> Path | None:
    for apps in (Path("/Applications"), Path.home() / "Applications"):
        app = apps / browser.mac_app
        if browser.mac_app and app.exists():
            return app
    return None


def _windows_executable(browser: Browser) -> Path | None:
    import winreg

    if browser.win_process:
        sub = f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{browser.win_process}"
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, sub) as key:
                    value, _ = winreg.QueryValueEx(key, "")
            except OSError:
                continue
            candidate = Path(str(value).strip('"'))
            if candidate.exists():
                return candidate
    for env_var, rel in browser.win_exe_candidates:
        base = os.environ.get(env_var)
        if base:
            candidate = Path(base) / rel
            if candidate.exists():
                return candidate
    return None


def is_installed_browser(browser: Browser) -> bool:
    if sys.platform == "darwin":
        return mac_app_path(browser) is not None or browser.key == "safari"
    return find_executable(browser) is not None
