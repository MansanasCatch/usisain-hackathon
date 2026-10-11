"""Per-browser extension install flows using only paths browsers officially allow.

* Chromium: open the store listing, or fall back to the extensions page plus
  "Load unpacked" instructions.
* Firefox: open the AMO listing or a signed .xpi, or fall back to
  about:debugging temporary loading.
* Safari: open the bundled Safari Web Extension wrapper app.

The launcher never edits browser profiles or writes install policies.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from usisain_launcher import detect
from usisain_launcher.browsers import Browser
from usisain_launcher.settings import (
    APP_NAME,
    CHROME_WEB_STORE_URL,
    EDGE_ADDONS_URL,
    FIREFOX_AMO_URL,
)

log = logging.getLogger(__name__)

SAFARI_WRAPPER_APP = f"{APP_NAME} Extension.app"
SIGNED_XPI = "usisain.xpi"


@dataclass
class InstallPlan:
    browser: Browser
    title: str
    url: str | None = None  # page to open in the target browser
    open_path: Path | None = None  # local file/app to open (xpi, Safari wrapper)
    steps: list[str] = field(default_factory=list)
    copy_text: str | None = None  # e.g. the folder to pick in "Load unpacked"
    is_store: bool = False


def store_url_for(browser: Browser) -> str:
    if browser.key == "edge":
        return EDGE_ADDONS_URL or CHROME_WEB_STORE_URL
    if browser.family == "chromium":
        return CHROME_WEB_STORE_URL
    if browser.family == "firefox":
        return FIREFOX_AMO_URL
    return ""


def plan_install(browser: Browser, folder: Path, platform: str | None = None) -> InstallPlan:
    """Build the install plan. ``folder`` is the built extension for the browser family."""
    platform = platform or sys.platform
    if browser.family == "chromium":
        return _plan_chromium(browser, folder)
    if browser.family == "firefox":
        return _plan_firefox(browser, folder)
    return _plan_safari(browser, folder, platform)


def _plan_chromium(browser: Browser, folder: Path) -> InstallPlan:
    store = store_url_for(browser)
    if store:
        return InstallPlan(
            browser=browser,
            title=f"Add {APP_NAME} from the store",
            url=store,
            is_store=True,
            steps=[
                f"{browser.name} opens the {APP_NAME} store page.",
                f'Click "Add to {browser.name.split()[-1]}" / "Get" and confirm.',
            ],
        )
    dev_toggle = (
        "Turn on Developer mode (left sidebar)."
        if browser.key == "edge"
        else "Turn on Developer mode (toggle in the top-right corner)."
    )
    return InstallPlan(
        browser=browser,
        title=f"Load {APP_NAME} into {browser.name}",
        url=browser.extensions_url,
        copy_text=str(folder),
        steps=[
            f"{browser.name} opens its Extensions page ({browser.extensions_url}).",
            dev_toggle,
            'Click "Load unpacked".',
            "Select this folder (already copied to your clipboard):\n" + str(folder),
            f"Optional: pin {APP_NAME} from the puzzle-piece menu.",
        ],
    )


def _plan_firefox(browser: Browser, folder: Path) -> InstallPlan:
    if FIREFOX_AMO_URL:
        return InstallPlan(
            browser=browser,
            title=f"Add {APP_NAME} from Firefox Add-ons",
            url=FIREFOX_AMO_URL,
            is_store=True,
            steps=['Click "Add to Firefox", then "Add" to confirm.'],
        )
    xpi = folder / SIGNED_XPI
    if xpi.is_file():
        return InstallPlan(
            browser=browser,
            title=f"Install the signed {APP_NAME} add-on",
            open_path=xpi,
            steps=['Firefox shows an install prompt. Click "Add".'],
        )
    manifest = folder / "manifest.json"
    return InstallPlan(
        browser=browser,
        title=f"Load {APP_NAME} into Firefox",
        url=browser.extensions_url,
        copy_text=str(manifest),
        steps=[
            'Firefox opens "about:debugging" > This Firefox.',
            'Click "Load Temporary Add-on...".',
            "Select this file (already copied to your clipboard):\n" + str(manifest),
            f"In about:addons > {APP_NAME} > Permissions, allow access to websites.",
            "Note: temporary add-ons are removed when Firefox restarts until the "
            "add-on is signed on addons.mozilla.org.",
        ],
    )


def _plan_safari(browser: Browser, folder: Path, platform: str) -> InstallPlan:
    wrapper = folder / SAFARI_WRAPPER_APP
    if platform == "darwin" and wrapper.exists():
        return InstallPlan(
            browser=browser,
            title=f"Enable {APP_NAME} in Safari",
            open_path=wrapper,
            steps=[
                f'The "{APP_NAME} Extension" app opens. Click "Quit and Open Safari Settings".',
                f"In Safari > Settings > Extensions, tick {APP_NAME}.",
                'Unsigned builds only: Safari > Settings > Advanced > "Show features for '
                'web developers", then Develop > "Allow Unsigned Extensions".',
                f'Click "Always Allow on Every Website" for {APP_NAME}.',
            ],
        )
    return InstallPlan(
        browser=browser,
        title=f"{APP_NAME} for Safari is not included in this build",
        steps=[
            "The Safari extension must be built on a Mac with Xcode.",
            "Run desktop/build_macos.sh on macOS to produce it.",
        ],
    )


# --------------------------------------------------------------------------- launching


def _detach_kwargs() -> dict[str, Any]:
    if sys.platform == "win32":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        return {"creationflags": flags, "close_fds": True}
    return {"start_new_session": True, "close_fds": True}


def open_in_browser(browser: Browser, url: str, load_ext_folder: Path | None = None) -> bool:
    """Open ``url`` in a specific browser. Internal pages need the browser binary."""
    try:
        if sys.platform == "darwin":
            app = detect.mac_app_path(browser)
            if browser.family == "safari" or (app and url.startswith("http")):
                cmd = ["open", "-a", str(app or "Safari")]
                if load_ext_folder and browser.family == "chromium":
                    cmd.extend(["--args", f"--load-extension={load_ext_folder}"])
                cmd.append(url)
                subprocess.Popen(cmd, **_detach_kwargs())
                return True
        exe = detect.find_executable(browser)
        if exe:
            cmd = [str(exe)]
            if load_ext_folder and browser.family == "chromium":
                cmd.append(f"--load-extension={load_ext_folder}")
            cmd.append(url)
            subprocess.Popen(cmd, **_detach_kwargs())
            return True
    except OSError as exc:
        log.warning("Could not launch %s: %s", browser.name, exc)
    if url.startswith("http"):
        return webbrowser.open(url)
    return False


def open_path(path: Path, browser: Browser | None = None) -> bool:
    try:
        if browser and path.suffix == ".xpi":
            exe = detect.find_executable(browser)
            if exe:
                subprocess.Popen([str(exe), str(path)], **_detach_kwargs())
                return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], **_detach_kwargs())
            return True
        if sys.platform == "win32":
            os.startfile(str(path))
            return True
    except OSError as exc:
        log.warning("Could not open %s: %s", path, exc)
    return False


def execute(plan: InstallPlan) -> bool:
    """Open the page/app described by ``plan``. Returns False if nothing could be opened."""
    if plan.open_path is not None:
        return open_path(plan.open_path, plan.browser)
    if plan.url:
        load_folder = (
            Path(plan.copy_text)
            if (plan.copy_text and not plan.is_store and plan.browser.family == "chromium")
            else None
        )
        return open_in_browser(plan.browser, plan.url, load_ext_folder=load_folder)
    return False
