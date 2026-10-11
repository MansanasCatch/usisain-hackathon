import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message=".*Field 'lifespan' has an incomplete definition.*")
_repo_root = str(Path(__file__).resolve().parents[3])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
_mcp_server = str(Path(__file__).resolve().parents[3] / "mcp_server")
if _mcp_server not in sys.path:
    sys.path.insert(0, _mcp_server)
