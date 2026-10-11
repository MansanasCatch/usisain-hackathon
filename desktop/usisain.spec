# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for UsisAIn Desktop Launcher & Server (Windows .exe and macOS .app)."""

import os
import sys
from pathlib import Path

# Base directories
SPEC_DIR = Path(SPEC).resolve().parent
REPO_ROOT = SPEC_DIR.parent

# Prepare stamp for runtime syncing
stamp_file = SPEC_DIR / "build" / "STAMP"
stamp_file.parent.mkdir(parents=True, exist_ok=True)
import hashlib, time
stamp_val = f"usisain-{int(time.time())}"
stamp_file.write_text(stamp_val, encoding="utf-8")

# Assets & Data files
datas = [
    (str(SPEC_DIR / "assets" / "icon-*.png"), "assets"),
    (str(SPEC_DIR / "assets" / "icon.ico"), "assets"),
    (str(SPEC_DIR / "assets" / "icon.icns"), "assets"),
    # Bundled payload for user runtime execution
    (str(REPO_ROOT / "backend-api"), "payload/backend-api"),
    (str(REPO_ROOT / "mcp_server"), "payload/mcp_server"),
    (str(REPO_ROOT / "client" / "web-app"), "payload/client/web-app"),
    (str(SPEC_DIR / "build" / "extension"), "payload/extension"),
    (str(REPO_ROOT / "data" / "scripts"), "payload/data/scripts"),
    (str(REPO_ROOT / ".env.example"), "payload"),
    (str(stamp_file), "payload"),
]

# Add backend-api/src and mcp_server to sys.path so collect_submodules can discover them
for p in [str(REPO_ROOT / "backend-api" / "src"), str(REPO_ROOT / "mcp_server"), str(SPEC_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from PyInstaller.utils.hooks import collect_submodules

hidden_imports = [
    # Launcher
    "usisain_launcher",
    "usisain_launcher.browsers",
    "usisain_launcher.config",
    "usisain_launcher.detect",
    "usisain_launcher.dialogs",
    "usisain_launcher.installed",
    "usisain_launcher.installer",
    "usisain_launcher.paths",
    "usisain_launcher.runtime",
    "usisain_launcher.settings",

    # Standard library modules used dynamically across backend, MCP and TTS
    "wave",
    "uuid",
    "tempfile",
    "queue",
    "contextvars",
    "concurrent",
    "concurrent.futures",
    "traceback",
    "base64",
    "datetime",
    "difflib",
    "sqlite3",
    "shutil",
    "socket",
    "urllib",
    "urllib.request",
    "urllib.parse",
    "urllib.error",
    "email",
    "email.mime",
    "email.mime.text",
    "email.mime.multipart",
    "http",
    "http.client",
    "http.server",
    "ssl",
    "hashlib",
    "hmac",
    "secrets",
    "random",
    "json",
    "csv",
    "plistlib",
    "ctypes",

    # Uvicorn & FastAPI core
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "fastapi",
    "fastapi.staticfiles",
    "fastapi.middleware.cors",
    "pydantic",
    "pydantic_settings",
    "starlette",
    "multipart",

    # MCP & Pipeline Tools
    "mcp",
    "mcp.server",
    "dotenv",
    "requests",
    "bs4",
    "PIL",
    "PIL.Image",
    "numpy",
    "cv2",
    "scipy",
    "scipy.fftpack",
    "faster_whisper",
    "ctranslate2",
    "pytesseract",
    "sklearn",
    "gtts",
    "pygame",
    "playsound",
    "google.generativeai",
    "ollama",
]

# Auto-collect all submodules for the backend and MCP pipeline
hidden_imports += collect_submodules("usisain_backend")
hidden_imports += collect_submodules("mcp_server")

a = Analysis(
    [str(SPEC_DIR / "usisain_launcher" / "__main__.py")],
    pathex=[
        str(SPEC_DIR),
        str(REPO_ROOT),
        str(REPO_ROOT / "backend-api" / "src"),
        str(REPO_ROOT / "mcp_server"),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "notebook",
        "IPython",
        "pytest",
        "ruff",
        "pyright",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe_icon = str(SPEC_DIR / "assets" / "icon.ico") if sys.platform == "win32" else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="UsisAIn",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=exe_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="UsisAIn",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="UsisAIn.app",
        icon=str(SPEC_DIR / "assets" / "icon.icns"),
        bundle_identifier="app.usisain.UsisAIn",
        info_plist={
            "CFBundleShortVersionString": "0.2.0",
            "CFBundleVersion": "0.2.0",
            "NSHighResolutionCapable": "True",
            "LSUIElement": "0",
        },
    )
