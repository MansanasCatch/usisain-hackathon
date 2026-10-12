"""One-click developer runner for UsisAIn.

Starts the FastAPI server, automatically preloads the browser extension,
and navigates directly to the App Dashboard.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

# Ensure backend and mcp modules are resolvable
for path in (ROOT_DIR / "backend-api" / "src", ROOT_DIR / "mcp_server", ROOT_DIR):
    str_path = str(path)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)

os.chdir(ROOT_DIR)

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    print("=" * 65)
    print("  UsisAIn - Autonomous Fact-Checking & Deepfake Verification")
    print(f"  Server:    http://127.0.0.1:{port}")
    print(f"  Dashboard: http://127.0.0.1:{port}/app/dashboard")
    print("  Extension: Preloading into default browser automatically...")
    print("=" * 65)

    try:
        uvicorn.run(
            "usisain_backend.main:app",
            host="127.0.0.1",
            port=port,
            reload=False,
            log_level="info",
        )
    except KeyboardInterrupt:
        print("\n[UsisAIn] Server stopped. Clean exit.")
    finally:
        os._exit(0)
