"""Static launcher settings. Fill in the store URLs once the extension is published."""

from __future__ import annotations

APP_NAME = "UsisAIn"
APP_ID = "app.usisain.UsisAIn"
APP_VERSION = "0.2.0"

BACKEND_HOST = "127.0.0.1"
# The browser extension and web app hard-code localhost:8000, so this is fixed.
BACKEND_PORT = 8000
BACKEND_URL = f"http://localhost:{BACKEND_PORT}"
WEB_APP_URL = f"{BACKEND_URL}/app/"
DASHBOARD_URL = f"{BACKEND_URL}/app/dashboard/"
HEALTH_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}/api/settings"

# Pinned via the public "key" in client/browser-extension/manifest.json.
CHROMIUM_EXTENSION_ID = "dndlahijonngmpkomafkmiainhmkplnp"
GECKO_EXTENSION_ID = "usisain@usisain.app"
SAFARI_EXTENSION_BUNDLE_ID = "app.usisain.UsisAIn.Extension"

# Leave empty while unpublished; the launcher then falls back to "Load unpacked".
CHROME_WEB_STORE_URL = ""
EDGE_ADDONS_URL = ""
FIREFOX_AMO_URL = ""
