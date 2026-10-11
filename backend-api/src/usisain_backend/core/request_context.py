from contextvars import ContextVar

REQUEST_ID: ContextVar[str | None] = ContextVar("usisain_request_id", default=None)
