from contextvars import ContextVar

# Per-request context propagated to async tasks. Tools executed in executor
# cannot receive ContextVar directly, so call_tool will capture the value
# and copy it into the executor thread local for downstream logging.
REQUEST_ID: ContextVar[str | None] = ContextVar("usisain_request_id", default=None)
