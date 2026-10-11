"""Main entry point for the UsisAIn desktop launcher."""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
import time
import tkinter as tk
import uuid
import wave
import webbrowser
from pathlib import Path

# Ensure standard library modules used dynamically by backend services are bundled
_ = (wave, sqlite3, uuid)

from usisain_launcher import (
    config as cfg_module,
)
from usisain_launcher import (
    detect,
    dialogs,
    installed,
    installer,
    paths,
    runtime,
)
from usisain_launcher.browsers import CHROME, Browser
from usisain_launcher.settings import (
    APP_NAME,
    BACKEND_HOST,
    BACKEND_PORT,
    DASHBOARD_URL,
    HEALTH_URL,
    WEB_APP_URL,
)


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "launcher.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def open_folder(path: Path) -> None:
    installer.open_path(path)


def handle_browser_extension_flow(root: tk.Tk) -> tuple[Browser | None, bool]:
    """Detect browser, prompt for extension if needed, and execute install flow.

    Returns a tuple of (chosen_browser, was_installed).
    """
    conf = cfg_module.LauncherConfig.load(paths.config_file())

    running = detect.running_browsers()
    default_b = detect.default_browser()

    chosen: Browser | None = None
    if len(running) > 1:
        preselect = next((b for b in running if b.key == conf.last_browser), None) or default_b
        chosen = dialogs.choose_browser(root, running, preselect=preselect, default=default_b)
    elif len(running) == 1:
        chosen = running[0]
    else:
        chosen = default_b

    if chosen is None:
        return None, False

    conf.last_browser = chosen.key
    conf.save(paths.config_file())

    already_installed = installed.is_installed(chosen)
    was_installed = bool(already_installed)

    if cfg_module.should_prompt(conf, already_installed):
        choice = dialogs.ask_install(root, chosen)
        if choice == "never":
            conf.dont_ask_again = True
            conf.save(paths.config_file())
        elif choice == "add":
            ext_folder = paths.extension_dir(chosen.family)
            plan = installer.plan_install(chosen, ext_folder)
            installer.execute(plan)
            if plan.steps and not plan.is_store:
                detected = dialogs.show_instructions(
                    root,
                    title=plan.title,
                    steps=plan.steps,
                    copy_text=plan.copy_text,
                    note="Keep this window open while following the steps in your browser.",
                    check_installed=lambda: installed.is_installed(chosen) is True,
                )
                was_installed = detected or bool(installed.is_installed(chosen))
            else:
                was_installed = True

    return chosen, was_installed


def main() -> None:
    # 1. Setup paths & logging
    log_dir = paths.log_dir()
    setup_logging(log_dir)
    log = logging.getLogger("usisain_launcher")
    log.info("Starting %s launcher (frozen=%s)", APP_NAME, paths.is_frozen())

    # 2. Hidden Tk root for status window
    root = tk.Tk()
    root.withdraw()
    assets = paths.assets_dir()
    dialogs.init(root, assets)

    server: runtime.BackendServer | None = None
    try:
        # Detect default or best available browser via fast registry lookup
        active_browser = detect.default_browser() or CHROME

        # Status window callbacks
        def on_open_app() -> None:
            if active_browser:
                installer.open_in_browser(active_browser, WEB_APP_URL)
            else:
                webbrowser.open(WEB_APP_URL)

        def on_open_dash() -> None:
            if active_browser:
                installer.open_in_browser(active_browser, DASHBOARD_URL)
            else:
                webbrowser.open(DASHBOARD_URL)

        def on_add_ext() -> None:
            b = active_browser or detect.default_browser() or CHROME
            ext_folder = paths.extension_dir(b.family)
            plan = installer.plan_install(b, ext_folder)
            installer.execute(plan)
            if plan.steps and not plan.is_store:
                dialogs.show_instructions(
                    root,
                    title=plan.title,
                    steps=plan.steps,
                    copy_text=plan.copy_text,
                    note="Follow the steps in your browser to load the extension.",
                )

        def on_open_logs() -> None:
            open_folder(paths.log_dir())

        def on_quit() -> None:
            log.info("Shutting down %s...", APP_NAME)
            if server:
                try:
                    server.stop(timeout=1.0)
                except Exception:
                    pass
            try:
                root.destroy()
            except Exception:
                pass
            os._exit(0)

        # 3. Setup and show Status Window immediately for instant visual feedback
        status_win = dialogs.StatusWindow(
            root=root,
            on_open_app=on_open_app,
            on_open_dashboard=on_open_dash,
            on_add_extension=on_add_ext,
            on_open_logs=on_open_logs,
            on_quit=on_quit,
        )
        status_win.set_state("starting", f"Starting {APP_NAME} services...")
        root.update()

        # 4. If running frozen bundle, sync payload to user data runtime dir
        runtime_dir = paths.runtime_root()
        if paths.is_frozen():
            payload = paths.payload_dir()
            log.info("Syncing payload from %s to %s", payload, runtime_dir)
            try:
                runtime.sync_payload(payload, runtime_dir)
            except runtime.LauncherError as err:
                log.error("Sync payload error: %s", err)
                dialogs.show_error(root, "Setup Error", str(err))
                sys.exit(1)

        # 5. Check backend port & start background server
        if runtime.port_in_use(BACKEND_HOST, BACKEND_PORT):
            if runtime.backend_healthy(HEALTH_URL):
                log.info("Existing UsisAIn backend is already running on port %s", BACKEND_PORT)
            else:
                msg = (
                    f"Port {BACKEND_PORT} is in use by another application.\n\n"
                    f"Please close any service using port {BACKEND_PORT} and restart {APP_NAME}."
                )
                log.error(msg)
                dialogs.show_error(root, "Port Conflict", msg)
                sys.exit(1)
        else:
            log.info("Starting background FastAPI backend server at %s", runtime_dir)
            server = runtime.BackendServer(runtime_dir, BACKEND_HOST, BACKEND_PORT)
            server.start()

        # 6. Wait for backend ready
        start_wait = time.time()
        ready = False
        while time.time() - start_wait < 30.0:
            if runtime.backend_healthy(HEALTH_URL):
                ready = True
                break
            if server is not None and server.error is not None:
                raise runtime.LauncherError(f"Backend failed to start: {server.error}")
            time.sleep(0.3)
            root.update()

        if not ready and not runtime.backend_healthy(HEALTH_URL):
            raise runtime.LauncherError("Backend timed out while starting.")

        # 7. Launch browser with extension preloaded and navigate straight to dashboard
        ext_folder = paths.extension_dir(active_browser.family if active_browser else "chromium")
        if active_browser is not None:
            installer.open_in_browser(active_browser, DASHBOARD_URL, load_ext_folder=ext_folder)
        else:
            webbrowser.open(DASHBOARD_URL)

        status_win.set_state("ready", f"Server active at http://{BACKEND_HOST}:{BACKEND_PORT}")

        # Start Tk mainloop
        root.mainloop()

    except Exception as exc:
        log.exception("Fatal launcher error")
        dialogs.show_error(root, "Unexpected Error", f"An unexpected error occurred:\n{exc}")
        if server:
            server.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
