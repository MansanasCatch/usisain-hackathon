"""Catalogue of supported browsers and where they live on each OS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Family = Literal["chromium", "firefox", "safari"]


@dataclass(frozen=True)
class Browser:
    key: str
    name: str
    family: Family
    extensions_url: str
    # Windows
    win_process: str = ""
    win_progid_prefixes: tuple[str, ...] = ()
    win_exe_candidates: tuple[tuple[str, str], ...] = ()  # (env var, relative path)
    win_user_data: tuple[str, str] | None = None  # (env var, relative path)
    # macOS
    mac_bundle_id: str = ""
    mac_app: str = ""  # e.g. "Google Chrome.app"
    mac_binary: str = ""  # executable inside Contents/MacOS
    mac_user_data: str | None = None  # relative to ~/Library/Application Support
    # Opera keeps a single profile directly in its user-data folder.
    user_data_is_profile: bool = False


CHROME = Browser(
    key="chrome",
    name="Google Chrome",
    family="chromium",
    extensions_url="chrome://extensions/",
    win_process="chrome.exe",
    win_progid_prefixes=("ChromeHTML",),
    win_exe_candidates=(
        ("PROGRAMFILES", "Google/Chrome/Application/chrome.exe"),
        ("PROGRAMFILES(X86)", "Google/Chrome/Application/chrome.exe"),
        ("LOCALAPPDATA", "Google/Chrome/Application/chrome.exe"),
    ),
    win_user_data=("LOCALAPPDATA", "Google/Chrome/User Data"),
    mac_bundle_id="com.google.chrome",
    mac_app="Google Chrome.app",
    mac_binary="Google Chrome",
    mac_user_data="Google/Chrome",
)

EDGE = Browser(
    key="edge",
    name="Microsoft Edge",
    family="chromium",
    extensions_url="edge://extensions/",
    win_process="msedge.exe",
    win_progid_prefixes=("MSEdgeHTM",),
    win_exe_candidates=(
        ("PROGRAMFILES(X86)", "Microsoft/Edge/Application/msedge.exe"),
        ("PROGRAMFILES", "Microsoft/Edge/Application/msedge.exe"),
    ),
    win_user_data=("LOCALAPPDATA", "Microsoft/Edge/User Data"),
    mac_bundle_id="com.microsoft.edgemac",
    mac_app="Microsoft Edge.app",
    mac_binary="Microsoft Edge",
    mac_user_data="Microsoft Edge",
)

BRAVE = Browser(
    key="brave",
    name="Brave",
    family="chromium",
    extensions_url="brave://extensions/",
    win_process="brave.exe",
    win_progid_prefixes=("BraveHTML",),
    win_exe_candidates=(
        ("PROGRAMFILES", "BraveSoftware/Brave-Browser/Application/brave.exe"),
        ("PROGRAMFILES(X86)", "BraveSoftware/Brave-Browser/Application/brave.exe"),
        ("LOCALAPPDATA", "BraveSoftware/Brave-Browser/Application/brave.exe"),
    ),
    win_user_data=("LOCALAPPDATA", "BraveSoftware/Brave-Browser/User Data"),
    mac_bundle_id="com.brave.browser",
    mac_app="Brave Browser.app",
    mac_binary="Brave Browser",
    mac_user_data="BraveSoftware/Brave-Browser",
)

OPERA = Browser(
    key="opera",
    name="Opera",
    family="chromium",
    extensions_url="opera://extensions",
    win_process="opera.exe",
    win_progid_prefixes=("OperaStable", "OperaGXStable", "Opera"),
    win_exe_candidates=(("LOCALAPPDATA", "Programs/Opera/launcher.exe"),),
    win_user_data=("APPDATA", "Opera Software/Opera Stable"),
    mac_bundle_id="com.operasoftware.opera",
    mac_app="Opera.app",
    mac_binary="Opera",
    mac_user_data="com.operasoftware.Opera",
    user_data_is_profile=True,
)

FIREFOX = Browser(
    key="firefox",
    name="Mozilla Firefox",
    family="firefox",
    extensions_url="about:debugging#/runtime/this-firefox",
    win_process="firefox.exe",
    win_progid_prefixes=("FirefoxURL", "FirefoxHTML"),
    win_exe_candidates=(
        ("PROGRAMFILES", "Mozilla Firefox/firefox.exe"),
        ("PROGRAMFILES(X86)", "Mozilla Firefox/firefox.exe"),
    ),
    win_user_data=("APPDATA", "Mozilla/Firefox/Profiles"),
    mac_bundle_id="org.mozilla.firefox",
    mac_app="Firefox.app",
    mac_binary="firefox",
    mac_user_data="Firefox/Profiles",
)

SAFARI = Browser(
    key="safari",
    name="Safari",
    family="safari",
    extensions_url="",
    mac_bundle_id="com.apple.safari",
    mac_app="Safari.app",
    mac_binary="Safari",
)

ALL_BROWSERS: tuple[Browser, ...] = (CHROME, EDGE, BRAVE, OPERA, FIREFOX, SAFARI)
BY_KEY: dict[str, Browser] = {b.key: b for b in ALL_BROWSERS}


def supported_on(platform: str) -> tuple[Browser, ...]:
    if platform == "darwin":
        return ALL_BROWSERS
    return tuple(b for b in ALL_BROWSERS if b.family != "safari")
