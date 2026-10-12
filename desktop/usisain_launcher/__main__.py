"""Main entry point for the UsisAIn desktop launcher."""

from __future__ import annotations

import json
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
        # Load user configuration
        conf = cfg_module.LauncherConfig.load(paths.config_file())
        current_port = conf.port
        os.environ["PORT"] = str(current_port)

        def get_urls(port: int) -> tuple[str, str, str, str]:
            base = f"http://localhost:{port}"
            return base, f"{base}/app/", f"{base}/app/dashboard/", f"http://{BACKEND_HOST}:{port}/api/settings"

        backend_url, web_app_url, dashboard_url, health_url = get_urls(current_port)

        def sync_extension_config(port: int) -> None:
            payload = json.dumps({"port": port, "url": f"http://localhost:{port}"}, indent=2)
            for variant in ("chromium", "firefox", "safari"):
                try:
                    ext_dir = paths.extension_dir(variant)
                    if ext_dir.is_dir():
                        (ext_dir / "backend.json").write_text(payload, encoding="utf-8")
                except OSError as e:
                    log.debug("Could not write backend.json in %s: %s", variant, e)

        sync_extension_config(current_port)

        # Detect default or best available browser via fast registry lookup
        active_browser = detect.default_browser() or CHROME

        # Status window callbacks
        def on_open_app() -> None:
            if active_browser:
                installer.open_in_browser(active_browser, web_app_url)
            else:
                webbrowser.open(web_app_url)

        def on_open_dash() -> None:
            if active_browser:
                installer.open_in_browser(active_browser, dashboard_url)
            else:
                webbrowser.open(dashboard_url)

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

        def on_change_port() -> None:
            nonlocal current_port, backend_url, web_app_url, dashboard_url, health_url, server
            new_port = dialogs.prompt_change_port(
                root,
                current_port=current_port,
                is_port_in_use=lambda p: runtime.port_in_use(BACKEND_HOST, p) and p != current_port,
            )
            if new_port is None or new_port == current_port:
                return

            log.info("Changing server port from %s to %s and restarting...", current_port, new_port)
            status_win.set_state("starting", f"Restarting server on port {new_port}...")
            root.update()

            if server:
                try:
                    server.stop(timeout=5.0)
                except Exception as exc:
                    log.warning("Error stopping server during port change: %s", exc)
                server = None

            time.sleep(0.5)
            root.update()

            current_port = new_port
            conf = cfg_module.LauncherConfig.load(paths.config_file())
            conf.port = new_port
            conf.save(paths.config_file())

            os.environ["PORT"] = str(new_port)
            try:
                from usisain_backend.core.config import settings
                settings.persist_env_var("PORT", str(new_port))
            except Exception as exc:
                log.warning("Could not persist PORT in .env: %s", exc)

            backend_url, web_app_url, dashboard_url, health_url = get_urls(new_port)
            sync_extension_config(new_port)

            try:
                server = runtime.BackendServer(runtime_dir, BACKEND_HOST, new_port)
                server.start()

                start_wait = time.time()
                ready = False
                while time.time() - start_wait < 30.0:
                    if runtime.backend_healthy(health_url):
                        ready = True
                        break
                    if server is not None and server.error is not None:
                        raise runtime.LauncherError(f"Backend failed to restart: {server.error}")
                    time.sleep(0.3)
                    root.update()

                if not ready and not runtime.backend_healthy(health_url):
                    raise runtime.LauncherError(f"Backend timed out while restarting on port {new_port}.")

                log.info("Server restarted successfully on port %s", new_port)
                status_win.set_state("ready", f"Server active at http://{BACKEND_HOST}:{new_port}")
                root.update()

            except Exception as exc:
                log.exception("Failed to restart backend on port %s", new_port)
                status_win.set_state("error", f"Failed to start on port {new_port}: {exc}")
                dialogs.show_error(root, "Restart Error", f"Failed to restart server on port {new_port}:\n{exc}")

        # 3. Setup and show Status Window immediately for instant visual feedback
        status_win = dialogs.StatusWindow(
            root=root,
            on_open_app=on_open_app,
            on_open_dashboard=on_open_dash,
            on_add_extension=on_add_ext,
            on_open_logs=on_open_logs,
            on_quit=on_quit,
            on_change_port=on_change_port,
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
        if runtime.port_in_use(BACKEND_HOST, current_port):
            if runtime.backend_healthy(health_url):
                log.info("Existing UsisAIn backend is already running on port %s", current_port)
            else:
                msg = (
                    f"Port {current_port} is in use by another application.\n\n"
                    f"Click 'Change port...' to use another port, or close the application using port {current_port}."
                )
                log.error(msg)
                status_win.set_state("error", f"Port {current_port} is in use by another application.")
                dialogs.show_error(root, "Port Conflict", msg)
        else:
            log.info("Starting background FastAPI backend server on port %s at %s", current_port, runtime_dir)
            server = runtime.BackendServer(runtime_dir, BACKEND_HOST, current_port)
            server.start()

        # 6. Wait for backend ready if server was started
        if server is not None:
            start_wait = time.time()
            ready = False
            while time.time() - start_wait < 30.0:
                if runtime.backend_healthy(health_url):
                    ready = True
                    break
                if server is not None and server.error is not None:
                    raise runtime.LauncherError(f"Backend failed to start: {server.error}")
                time.sleep(0.3)
                root.update()

            if not ready and not runtime.backend_healthy(health_url):
                raise runtime.LauncherError("Backend timed out while starting.")

        if runtime.backend_healthy(health_url):
            # 7. Launch browser with extension preloaded and navigate straight to dashboard
            ext_folder = paths.extension_dir(active_browser.family if active_browser else "chromium")
            if active_browser is not None:
                installer.open_in_browser(active_browser, dashboard_url, load_ext_folder=ext_folder)
            else:
                webbrowser.open(dashboard_url)

            status_win.set_state("ready", f"Server active at http://{BACKEND_HOST}:{current_port}")

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
