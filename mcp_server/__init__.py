import warnings

# Suppress harmless pydantic_settings forward-ref warnings on Python 3.14
warnings.filterwarnings("ignore", message=".*Field 'lifespan' has an incomplete definition.*")

# Pydantic 2.14 compatibility shim for MCP FastMCP
try:
    import pydantic._internal._typing_extra as _te
    if not hasattr(_te, "eval_type_backport"):
        _te.eval_type_backport = getattr(_te, "eval_type_lenient", getattr(_te, "eval_type", None))
except Exception:
    pass
