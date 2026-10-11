from usisain_backend.app_factory import create_app
from usisain_backend.services.bootstrap_service import (
    auto_configure_fallback_ai,
    ensure_ollama_model,
)

_ensure_ollama_model = ensure_ollama_model
_auto_configure_fallback_ai = auto_configure_fallback_ai
app = create_app()
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("usisain_backend.main:app", host="0.0.0.0", port=8000, reload=True)
