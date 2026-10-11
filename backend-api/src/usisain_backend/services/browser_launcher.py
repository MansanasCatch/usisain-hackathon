"""Cross-platform automated browser launcher with UsisAIn extension preloaded.

Supports both developer mode (running from source) and packaged mode (.exe / .app).
Detects the best available browser (Chrome, Edge, Brave, Opera, Firefox) via fast
registry/OS lookups, preloads the extension using `--load-extension`, and navigates
directly to the UsisAIn App Dashboard.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LAUNCH_LOCK = threading.Lock()
_ALREADY_LAUNCHED = False


def _find_windows_browser() -> tuple[Path | None, bool]:
    """Find the best browser on Windows via fast registry lookups (~0.3ms).

    Returns (executable_path, is_chromium).
    """
    import winreg

    progid = ""
    for scheme in ("http", "https"):
        key_path = (
            f"Software\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\{scheme}\\UserChoice"
        )
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                val, _ = winreg.QueryValueEx(key, "ProgId")
                progid = str(val).lower()
                if progid:
                    break
        except OSError:
            continue

    def get_app_path(exe_name: str) -> Path | None:
        sub = f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe_name}"
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, sub) as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    clean_path = Path(str(val).strip('"'))
                    if clean_path.is_file():
                        return clean_path
            except OSError:
                continue
        # Also check standard Program Files directories
        for env_var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(env_var)
            if not base:
                continue
            candidates = [
                Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe",
                Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                Path(base) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
            ]
            for candidate in candidates:
                if candidate.name.lower() == exe_name.lower() and candidate.is_file():
                    return candidate
        return None

    # Check preferred based on user choice
    if "chrome" in progid:
        exe = get_app_path("chrome.exe")
        if exe:
            return exe, True
    elif "edge" in progid or "appx" in progid:
        exe = get_app_path("msedge.exe")
        if exe:
            return exe, True
    elif "brave" in progid:
        exe = get_app_path("brave.exe")
        if exe:
            return exe, True
    elif "firefox" in progid:
        exe = get_app_path("firefox.exe")
        if exe:
            return exe, False

    # Fallback priority scan (Chrome -> Edge -> Brave -> Opera -> Firefox)
    for exe_name, is_chrom in [
        ("chrome.exe", True),
        ("msedge.exe", True),
        ("brave.exe", True),
        ("launcher.exe", True),  # Opera
        ("firefox.exe", False),
    ]:
        found = get_app_path(exe_name)
        if found:
            return found, is_chrom

    return None, False


def _find_mac_browser() -> tuple[Path | None, bool]:
    """Find installed browser on macOS."""
    candidates = [
        (Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"), True),
        (Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"), True),
        (Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"), True),
        (Path("/Applications/Firefox.app/Contents/MacOS/firefox"), False),
    ]
    for binary, is_chrom in candidates:
        if binary.is_file():
            return binary, is_chrom
    return None, False


def _find_linux_browser() -> tuple[Path | None, bool]:
    """Find installed browser on Linux."""
    candidates = [
        ("google-chrome", True),
        ("microsoft-edge", True),
        ("brave-browser", True),
        ("chromium-browser", True),
        ("chromium", True),
        ("firefox", False),
    ]
    for name, is_chrom in candidates:
        which = shutil.which(name)
        if which:
            return Path(which), is_chrom
    return None, False


def find_browser() -> tuple[Path | None, bool]:
    """Locate the best browser executable and whether it supports Chromium flags."""
    if sys.platform == "win32":
        return _find_windows_browser()
    if sys.platform == "darwin":
        return _find_mac_browser()
    return _find_linux_browser()


def locate_extension_dir(project_root: Path) -> Path | None:
    """Find the unpacked Chromium extension directory."""
    candidates = [
        project_root / "client" / "browser-extension",
        project_root / "desktop" / "build" / "extension" / "chromium",
        Path(sys.executable).parent / "_internal" / "payload" / "extension" / "chromium",
        Path(sys.executable).parent / "_internal" / "payload" / "client" / "browser-extension",
    ]
    for c in candidates:
        if c.is_dir() and (c / "manifest.json").is_file():
            return c.resolve()
    return None


def open_browser_with_extension(
    target_url: str = "http://localhost:8000/app/dashboard",
    project_root: Path | None = None,
) -> bool:
    """Launch the browser with the UsisAIn extension preloaded and navigate to the dashboard."""
    global _ALREADY_LAUNCHED

    with _LAUNCH_LOCK:
        if _ALREADY_LAUNCHED:
            return True
        _ALREADY_LAUNCHED = True

    if os.environ.get("USISAIN_DISABLE_AUTO_BROWSER", "").strip() in ("1", "true", "yes"):
        logger.info("[Browser] Auto-open browser is disabled via USISAIN_DISABLE_AUTO_BROWSER")
        return False

    if project_root is None:
        from usisain_backend.core.config import settings

        project_root = settings.project_root

    ext_dir = locate_extension_dir(project_root)
    browser_exe, is_chromium = find_browser()

    logger.info(
        "[Browser] Launching browser (exe=%s, is_chromium=%s, ext_dir=%s)",
        browser_exe,
        is_chromium,
        ext_dir,
    )

    try:
        if browser_exe and is_chromium and ext_dir:
            cmd = [str(browser_exe), f"--load-extension={ext_dir}", target_url]
            kwargs: dict[str, Any] = {"close_fds": True}
            if sys.platform == "win32":
                flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0
                )
                kwargs["creationflags"] = flags
            else:
                kwargs["start_new_session"] = True
            subprocess.Popen(cmd, **kwargs)
            logger.info("[Browser] Successfully spawned %s with extension", browser_exe.name)
            return True
        elif browser_exe:
            cmd = [str(browser_exe), target_url]
            kwargs = {"close_fds": True}
            if sys.platform == "win32":
                kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0)
            subprocess.Popen(cmd, **kwargs)
            logger.info("[Browser] Spawned %s navigating to %s", browser_exe.name, target_url)
            return True
    except Exception as exc:
        logger.warning("[Browser] Could not spawn browser binary directly: %s", exc)

    # Fallback to standard webbrowser
    try:
        webbrowser.open(target_url)
        return True
    except Exception as exc:
        logger.error("[Browser] Failed to open URL via webbrowser: %s", exc)
        return False


async def schedule_browser_launch(
    target_url: str = "http://localhost:8000/app/dashboard",
    delay_seconds: float = 1.0,
) -> None:
    """Asynchronously wait for the server to be listening, then open the browser."""
    await asyncio.sleep(delay_seconds)
    open_browser_with_extension(target_url=target_url)
