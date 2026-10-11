"""Unit tests for UsisAIn desktop launcher, browser detection, installer, and runtime sync."""

from __future__ import annotations

import json
from pathlib import Path

from usisain_launcher import (
    browsers,
    detect,
    installed,
    installer,
    runtime,
)
from usisain_launcher import (
    config as cfg,
)

from desktop.tools import build_extension

# --------------------------------------------------------------------------- Config tests


def test_config_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    c = cfg.LauncherConfig.load(path)
    assert not c.dont_ask_again
    assert c.last_browser is None


def test_config_save_and_reload(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    c = cfg.LauncherConfig(dont_ask_again=True, last_browser="chrome")
    assert c.save(path)
    loaded = cfg.LauncherConfig.load(path)
    assert loaded.dont_ask_again is True
    assert loaded.last_browser == "chrome"


def test_config_corrupt_file_graceful(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{invalid json", encoding="utf-8")
    loaded = cfg.LauncherConfig.load(path)
    assert not loaded.dont_ask_again
    assert loaded.last_browser is None


def test_should_prompt_logic() -> None:
    # If user selected "don't ask again", never prompt
    assert not cfg.should_prompt(cfg.LauncherConfig(dont_ask_again=True), installed=False)
    assert not cfg.should_prompt(cfg.LauncherConfig(dont_ask_again=True), installed=None)

    # If extension is definitely installed, don't prompt
    assert not cfg.should_prompt(cfg.LauncherConfig(dont_ask_again=False), installed=True)

    # If extension is not installed or unknown, prompt
    assert cfg.should_prompt(cfg.LauncherConfig(dont_ask_again=False), installed=False)
    assert cfg.should_prompt(cfg.LauncherConfig(dont_ask_again=False), installed=None)


# --------------------------------------------------------------------------- Detection tests


def test_parse_tasklist_windows() -> None:
    tasklist_sample = (
        '"System Idle Process","0","Services","0","8 K"\n'
        '"chrome.exe","1234","Console","1","100,000 K"\n'
        '"msedge.exe","5678","Console","1","120,000 K"\n'
        '"svchost.exe","9999","Services","0","20,000 K"\n'
    )
    running = detect.parse_tasklist(tasklist_sample, platform="win32")
    keys = [b.key for b in running]
    assert "chrome" in keys
    assert "edge" in keys
    assert "firefox" not in keys


def test_parse_ps_macos() -> None:
    ps_sample = (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome\n"
        "/System/Applications/Utilities/Terminal.app/Contents/MacOS/Terminal\n"
    )
    running = detect.parse_ps(ps_sample)
    keys = [b.key for b in running]
    assert "chrome" in keys
    assert "firefox" not in keys


def test_browser_from_progid() -> None:
    assert detect.browser_from_progid("ChromeHTML.ABCDEF") == browsers.CHROME
    assert detect.browser_from_progid("MSEdgeHTM") == browsers.EDGE
    assert detect.browser_from_progid("FirefoxURL-12345") == browsers.FIREFOX
    assert detect.browser_from_progid("BraveHTML") == browsers.BRAVE
    assert detect.browser_from_progid("OperaStable") == browsers.OPERA
    assert detect.browser_from_progid("UnknownBrowser") is None


def test_default_from_launchservices() -> None:
    data = {
        "LSHandlers": [
            {
                "LSHandlerURLScheme": "mailto",
                "LSHandlerRoleAll": "com.apple.mail",
            },
            {
                "LSHandlerURLScheme": "https",
                "LSHandlerRoleAll": "com.google.chrome",
            },
        ]
    }
    b = detect.default_from_launchservices(data)
    assert b == browsers.CHROME


# --------------------------------------------------------------------------- Installed checks


def test_chromium_installed_check(tmp_path: Path) -> None:
    profile = tmp_path / "Default"
    profile.mkdir(parents=True)
    pref_file = profile / "Preferences"

    ext_id = "testextensionid123"
    pref_file.write_text(
        json.dumps({"extensions": {"settings": {ext_id: {"path": "dummy"}}}}),
        encoding="utf-8",
    )

    assert installed.chromium_has_extension([profile], ext_id) is True
    assert installed.chromium_has_extension([profile], "otherid") is False
    assert installed.chromium_has_extension([tmp_path / "NonExistent"], ext_id) is None


def test_firefox_installed_check(tmp_path: Path) -> None:
    profiles_dir = tmp_path / "Profiles"
    p1 = profiles_dir / "abc.default-release"
    p1.mkdir(parents=True)
    ext_json = p1 / "extensions.json"

    gecko_id = "test@usisain.app"
    ext_json.write_text(
        json.dumps({"addons": [{"id": gecko_id, "name": "UsisAIn"}]}),
        encoding="utf-8",
    )

    assert installed.firefox_has_extension(profiles_dir, gecko_id) is True
    assert installed.firefox_has_extension(profiles_dir, "other@addon") is False


# --------------------------------------------------------------------------- Installer plan


def test_plan_install_chromium_unpacked(tmp_path: Path) -> None:
    ext_folder = tmp_path / "chromium"
    plan = installer.plan_install(browsers.CHROME, ext_folder)
    assert not plan.is_store
    assert plan.url == "chrome://extensions/"
    assert plan.copy_text == str(ext_folder)
    assert any("Load unpacked" in s for s in plan.steps)


def test_plan_install_firefox(tmp_path: Path) -> None:
    ext_folder = tmp_path / "firefox"
    plan = installer.plan_install(browsers.FIREFOX, ext_folder)
    assert "about:debugging" in str(plan.url)
    assert any("Temporary Add-on" in s for s in plan.steps)


# --------------------------------------------------------------------------- Runtime sync


def test_sync_payload_protects_user_data(tmp_path: Path) -> None:
    payload = tmp_path / "payload"
    target = tmp_path / "runtime"
    payload.mkdir()

    # Create dummy payload files
    (payload / runtime.STAMP_NAME).write_text("v1.0.0", encoding="utf-8")
    (payload / "backend-api").mkdir()
    (payload / "backend-api" / "code.py").write_text("print(1)", encoding="utf-8")
    (payload / ".env.example").write_text("FOO=BAR\n", encoding="utf-8")

    # Target already has user's existing data and .env
    target.mkdir()
    (target / "data").mkdir()
    (target / "data" / "app.db").write_text("existing-database", encoding="utf-8")
    (target / ".env").write_text("FOO=CUSTOM_USER_KEY\n", encoding="utf-8")

    # Run sync
    refreshed = runtime.sync_payload(payload, target)
    assert refreshed is True

    # Check that code was synced
    assert (target / "backend-api" / "code.py").read_text(encoding="utf-8") == "print(1)"

    # Check that user data and .env were PRESERVED
    assert (target / "data" / "app.db").read_text(encoding="utf-8") == "existing-database"
    assert (target / ".env").read_text(encoding="utf-8") == "FOO=CUSTOM_USER_KEY\n"

    # Second sync with same stamp should not refresh
    assert runtime.sync_payload(payload, target) is False


# --------------------------------------------------------------------------- Extension build validation


def test_validate_manifest() -> None:
    valid_manifest = {
        "manifest_version": 3,
        "name": "UsisAIn",
        "version": "0.2.0",
        "icons": {},
        "action": {},
        "background": {},
    }
    errors = build_extension.validate_manifest(valid_manifest, Path("."), "chromium")
    assert errors == []

    invalid_manifest = {
        "manifest_version": 2,
        "name": "",
    }
    errors = build_extension.validate_manifest(invalid_manifest, Path("."), "chromium")
    assert len(errors) >= 2


# --------------------------------------------------------------------------- Browser launcher service


def test_browser_launcher_discovery() -> None:
    import sys

    # Add backend-api/src to sys.path if not present
    backend_src = str(Path(__file__).resolve().parent.parent / "backend-api" / "src")
    if backend_src not in sys.path:
        sys.path.insert(0, backend_src)

    from usisain_backend.services import browser_launcher

    browser_exe, is_chrom = browser_launcher.find_browser()
    # Should not throw, and on Windows test machine it should find Chrome or Edge
    assert browser_exe is None or browser_exe.is_file()

    project_root = Path(__file__).resolve().parent.parent
    ext_dir = browser_launcher.locate_extension_dir(project_root)
    assert ext_dir is not None
    assert (ext_dir / "manifest.json").is_file()


def test_browser_launcher_disable_flag(monkeypatch) -> None:
    import sys

    backend_src = str(Path(__file__).resolve().parent.parent / "backend-api" / "src")
    if backend_src not in sys.path:
        sys.path.insert(0, backend_src)

    from usisain_backend.services import browser_launcher

    monkeypatch.setenv("USISAIN_DISABLE_AUTO_BROWSER", "1")
    # Reset launch flag for testing
    browser_launcher._ALREADY_LAUNCHED = False

    res = browser_launcher.open_browser_with_extension()
    assert res is False


def test_model_vision_detection() -> None:
    from mcp_server.shared.model_utils import get_text_only_model_notice, model_supports_vision

    assert model_supports_vision("gemini", "gemini-2.5-flash") is True
    assert model_supports_vision("gemini", "gemini-3.5-flash") is True
    assert model_supports_vision("grok", "gpt-oss-120b") is False
    assert model_supports_vision("grok", "openai/gpt-oss-120b") is False
    assert model_supports_vision("grok", "grok-4.1-fast") is False
    assert model_supports_vision("grok", "grok-2-vision-1212") is True
    assert model_supports_vision("grok", "llama-3.2-11b-vision-preview") is True
    assert model_supports_vision("ollama", "llama3.2:1b") is False
    assert model_supports_vision("ollama", "moondream") is True

    # Test notices in multiple supported languages
    notice_en = get_text_only_model_notice("gpt-oss-120b", "english")
    assert "gpt-oss-120b" in notice_en
    assert "text-only" in notice_en.lower()

    notice_tl = get_text_only_model_notice("gpt-oss-120b", "tagalog")
    assert "Larawan na walang text overlay" in notice_tl

    notice_ceb = get_text_only_model_notice("gpt-oss-120b", "cebuano")
    assert "Hulagway nga walay text overlay" in notice_ceb

    notice_ilo = get_text_only_model_notice("gpt-oss-120b", "ilocano")
    assert "Ladawan nga awan ti text overlay" in notice_ilo


