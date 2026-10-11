import warnings

warnings.filterwarnings("ignore", message=".*Field 'lifespan' has an incomplete definition.*")
try:
    import pydantic._internal._typing_extra as _te

    if not hasattr(_te, "eval_type_backport"):
        _te.eval_type_backport = getattr(_te, "eval_type_lenient", getattr(_te, "eval_type", None))
except Exception:
    pass
