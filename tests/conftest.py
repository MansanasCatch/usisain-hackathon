import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_SRC = ROOT / "backend-api" / "src"
MCP_SRC = ROOT
for p in (str(BACKEND_SRC), str(MCP_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)
