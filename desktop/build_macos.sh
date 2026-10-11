#!/usr/bin/env bash
# macOS build script for UsisAIn (.app, .dmg, Safari Web Extension converter)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=========================================================="
echo "          Building UsisAIn Desktop Bundle (macOS)         "
echo "=========================================================="

PYTHON="${PYTHON:-python3}"
if [ -f "${REPO_ROOT}/venv/bin/python" ]; then
    PYTHON="${REPO_ROOT}/venv/bin/python"
fi

echo "[1/6] Using Python: $PYTHON"

# 1. Generate icons
if [ ! -f "${SCRIPT_DIR}/assets/icon.icns" ]; then
    echo "[2/6] Generating icon assets..."
    "$PYTHON" "${SCRIPT_DIR}/tools/make_icons.py"
else
    echo "[2/6] Icon assets already generated."
fi

# 2. Build extensions
echo "[3/6] Building & validating browser extensions..."
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH:-}"
"$PYTHON" "${SCRIPT_DIR}/tools/build_extension.py"

# 3. Safari Web Extension wrapper (if Xcode available)
if command -v xcrun >/dev/null 2>&1 && xcrun --find safari-web-extension-converter >/dev/null 2>&1; then
    echo "[4/6] Converting Chromium extension to Safari Web Extension..."
    SAFARI_OUT="${SCRIPT_DIR}/build/extension/safari"
    rm -rf "$SAFARI_OUT"
    mkdir -p "$SAFARI_OUT"
    xcrun safari-web-extension-converter \
        --macos-only \
        --app-name "UsisAIn Extension" \
        --bundle-identifier "app.usisain.UsisAIn.Extension" \
        --no-open \
        --no-prompt \
        --output "$SAFARI_OUT" \
        "${SCRIPT_DIR}/build/extension/chromium" || echo "Warning: Safari converter returned non-zero, continuing..."
else
    echo "[4/6] xcrun safari-web-extension-converter not available. Skipping Safari wrapper build."
fi

# 4. PyInstaller
echo "[5/6] Running PyInstaller..."
DIST_DIR="${SCRIPT_DIR}/dist"
WORK_DIR="${SCRIPT_DIR}/build/pyinstaller"

"$PYTHON" -m PyInstaller \
    --distpath "$DIST_DIR" \
    --workpath "$WORK_DIR" \
    --noconfirm \
    --clean \
    "${SCRIPT_DIR}/usisain.spec"

APP_PATH="${DIST_DIR}/UsisAIn.app"
if [ ! -d "$APP_PATH" ]; then
    echo "Error: Output $APP_PATH not found" >&2
    exit 1
fi
echo "[OK] Built $APP_PATH"

# 5. Create DMG
echo "[6/6] Packaging DMG archive..."
DMG_PATH="${DIST_DIR}/UsisAIn-macOS.dmg"
rm -f "$DMG_PATH"

if command -v hdiutil >/dev/null 2>&1; then
    hdiutil create -volname "UsisAIn" -srcfolder "$APP_PATH" -ov -format UDZO "$DMG_PATH"
    echo "[OK] Created $DMG_PATH"
else
    echo "hdiutil not found, skipping DMG creation."
fi

echo "=========================================================="
echo " Build Complete: $APP_PATH"
echo "=========================================================="
