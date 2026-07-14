"""client.py — calls MCP server tools directly in-process (no subprocess).

On Windows, asyncio's ProactorEventLoop cannot spawn subprocesses from within
a uvicorn worker thread, so the MCP stdio_client approach raises
NotImplementedError. Instead we import the tool functions directly and call
them in a thread-pool executor so sync Ollama/httpx calls don't block the
event loop.
"""

import sys
import asyncio
import threading

from ...core.config import settings
from ...core.request_context import REQUEST_ID

# Make sure the mcp_server package is importable.
# settings.project_root is always an absolute, resolved Path.
_mcp_server_root = settings.project_root / "mcp_server"
if str(_mcp_server_root) not in sys.path:
    sys.path.insert(0, str(_mcp_server_root))

from tools.step1_ai_insights import generate_insight          # noqa: E402
from tools.step2_content_analyser import analyze_content      # noqa: E402
from tools.step3_legit_or_fake import check_claim             # noqa: E402
from tools.step4_actionable_items import generate_actions     # noqa: E402
from tools.step5_learnings import generate_learnings          # noqa: E402

_TOOL_MAP = {
    "step1_ai_insights": generate_insight,
    "step2_content_analyser": analyze_content,
    "step3_legit_or_fake": check_claim,
    "step4_actionable_items": generate_actions,
    "step5_learnings": generate_learnings,
}

# Executor thread-local context used to transfer request metadata into the
# worker thread that running tool functions (they run in a ThreadPoolExecutor).
_EXEC_CTX = threading.local()


async def call_tool(tool_name: str, arguments: dict) -> dict:
    """Call an MCP tool function directly in a thread-pool executor."""
    fn = _TOOL_MAP.get(tool_name)
    if fn is None:
        return {"error": f"Unknown tool: {tool_name}"}

    # Capture current request id (if any) from the async context and
    # copy it into the executor thread local before invoking the tool.
    req_id = None
    try:
        req_id = REQUEST_ID.get()
    except Exception:
        req_id = None

    def _run():
        try:
            # Propagate request id into this worker thread for logging
            _EXEC_CTX.request_id = req_id
        except Exception:
            pass
        return fn(**arguments)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _run)
    if isinstance(result, dict):
        return result
    return {"raw": str(result)}
