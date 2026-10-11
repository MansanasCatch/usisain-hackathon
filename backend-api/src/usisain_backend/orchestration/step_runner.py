import asyncio
import logging
import traceback

from usisain_backend.core.config import settings
from usisain_backend.data.repositories.errors_repository import ErrorsRepository
from usisain_backend.services.mcp_client.client import call_tool

logger = logging.getLogger(__name__)
STEP_INFO: dict[str, tuple[int, str]] = {
    "step1_ai_insights": (1, "ai_insights"),
    "step2_content_analyser": (2, "content_analyser"),
    "step3_legit_or_fake": (3, "legit_or_fake"),
    "step4_actionable_items": (4, "actionable_items"),
    "step5_learnings": (5, "learnings"),
}
_errors_repo = ErrorsRepository()


async def execute_step(
    tool_name: str, arguments: dict, timeout_seconds: float | None = None
) -> dict:
    timeout = (
        timeout_seconds if timeout_seconds is not None else settings.pipeline_step_timeout_seconds
    )
    step_num, step_name = STEP_INFO.get(tool_name, (None, tool_name))
    try:
        result = await asyncio.wait_for(call_tool(tool_name, arguments), timeout=timeout)
        if isinstance(result, dict) and result.get("error"):
            _errors_repo.insert(
                step=step_num,
                step_name=step_name,
                error_msg=result["error"],
                error_type="pipeline",
                details=f"Tool: {tool_name}",
            )
        return result
    except asyncio.TimeoutError:
        err_msg = f"Step timed out after {timeout:.0f} seconds."
        _errors_repo.insert(
            step=step_num,
            step_name=step_name,
            error_msg=err_msg,
            error_type="pipeline_timeout",
            details=f"Tool: {tool_name} timed out after {timeout:.0f} seconds.",
        )
        return {"error": err_msg}
    except Exception as e:
        tb = traceback.format_exc()
        logger.exception("Error calling tool %s", tool_name)
        err_msg = str(e).strip() or f"Unexpected error: {type(e).__name__}"
        _errors_repo.insert(
            step=step_num, step_name=step_name, error_msg=err_msg, error_type="pipeline", details=tb
        )
        return {"error": err_msg}


def get_step_status(result: dict) -> str:
    return "error" if isinstance(result, dict) and result.get("error") else "completed"
