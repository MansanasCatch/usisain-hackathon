"""Prepare the writable runtime folder and run the FastAPI backend in-process.

The backend and MCP pipeline resolve ``data/``, ``.env`` and the vector store
relative to their own source files. Running them from a writable copy of the
bundled source keeps those paths valid without touching app logic.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

STAMP_NAME = "STAMP"
LOCAL_STAMP = ".bundle_stamp"
# Code folders are replaced whenever the bundle changes.
CODE_ENTRIES = ("backend-api", "mcp_server", "client", "extension")
# Runtime data folders are created if missing and never overwritten.
DATA_SUBDIRS = ("uploads", "reference_images", "vector_index", "models", "tts_output")


class LauncherError(Exception):
    """An error with a message that is safe to show to the user."""


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def sync_payload(payload: Path, target: Path) -> bool:
    """Copy bundled code into ``target``. Returns True when files were refreshed.

    ``data/`` contents (database, uploads, vector index) and ``.env`` are kept.
    """
    stamp = _read_text(payload / STAMP_NAME)
    if not payload.is_dir() or not stamp:
        raise LauncherError(
            "The application bundle is incomplete. Please re-download or rebuild UsisAIn."
        )
    try:
        target.mkdir(parents=True, exist_ok=True)
        refreshed = False
        if _read_text(target / LOCAL_STAMP) != stamp:
            log.info("Syncing application files to %s", target)
            for name in CODE_ENTRIES:
                src, dst = payload / name, target / name
                if dst.exists():
                    shutil.rmtree(dst)
                if src.exists():
                    shutil.copytree(src, dst)
            scripts_src = payload / "data" / "scripts"
            scripts_dst = target / "data" / "scripts"
            if scripts_dst.exists():
                shutil.rmtree(scripts_dst)
            if scripts_src.exists():
                shutil.copytree(scripts_src, scripts_dst)
            example = payload / ".env.example"
            if example.exists():
                shutil.copy2(example, target / ".env.example")
            refreshed = True
        ensure_runtime_files(target)
        if refreshed:
            (target / LOCAL_STAMP).write_text(stamp, encoding="utf-8")
        return refreshed
    except PermissionError as exc:
        raise LauncherError(
            f"UsisAIn does not have permission to write to:\n{exc.filename or target}\n\n"
            "Check the folder permissions or free up disk space, then try again."
        ) from exc
    except OSError as exc:
        raise LauncherError(f"Could not prepare application files:\n{exc}") from exc


def ensure_runtime_files(root: Path) -> None:
    for sub in DATA_SUBDIRS:
        (root / "data" / sub).mkdir(parents=True, exist_ok=True)
    env_file, example = root / ".env", root / ".env.example"
    if not env_file.exists() and example.exists():
        shutil.copy2(example, env_file)
        log.info("Created %s from .env.example", env_file)


# --------------------------------------------------------------------------- networking


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def backend_healthy(url: str, timeout: float = 2.0) -> bool:
    """True when ``url`` answers with JSON, i.e. a UsisAIn backend is serving."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                return False
            json.loads(resp.read().decode("utf-8", errors="replace") or "null")
            return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


# --------------------------------------------------------------------------- server


class BackendServer:
    """Runs ``usisain_backend.main:app`` with uvicorn on a background thread."""

    def __init__(self, root: Path, host: str, port: int) -> None:
        self.root = root
        self.host = host
        self.port = port
        self.error: BaseException | None = None
        self._server: Any = None
        self._thread: threading.Thread | None = None

    def _prepare_imports(self) -> None:
        for entry in (self.root / "backend-api" / "src", self.root):
            path = str(entry)
            if path not in sys.path:
                sys.path.insert(0, path)
        os.chdir(self.root)

    def start(self) -> None:
        self._prepare_imports()
        import uvicorn

        config = uvicorn.Config(
            "usisain_backend.main:app",
            host=self.host,
            port=self.port,
            log_config=None,
            use_colors=False,
            reload=False,
            workers=1,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._run, name="usisain-backend", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            self._server.run()
        except BaseException as exc:  # SystemExit from uvicorn on import errors, etc.
            self.error = exc
            log.exception("Backend server stopped with an error")

    @property
    def started(self) -> bool:
        return bool(self._server is not None and self._server.started)

    @property
    def alive(self) -> bool:
        return bool(self._thread is not None and self._thread.is_alive())

    def stop(self, timeout: float = 10.0) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout)
