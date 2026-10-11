import logging
import os
import urllib.request
from usisain_backend.core.config import settings

logger = logging.getLogger(__name__)


def ensure_ollama_model(model_name: str) -> bool:
    host = settings.ollama_host
    probe_url = f"{host.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(probe_url, method="GET")
        with urllib.request.urlopen(req, timeout=1.0):
            pass
    except Exception:
        logger.warning(
            "[Ollama] Daemon at %s is not reachable or not installed", host
        )
        return False

    import ollama

    client = ollama.Client(host=host)
    try:
        models = client.list()
    except Exception as e:
        logger.warning("[Ollama] Daemon at %s is not reachable: %s", host, e)
        return False

    available = []
    if hasattr(models, "models"):
        available = [m.model for m in models.models]
    elif isinstance(models, dict) and "models" in models:
        available = [
            m.get("model", m.get("name", "")) for m in models["models"]
        ]
    elif isinstance(models, list):
        available = [
            m.model if hasattr(m, "model") else m.get("model", "")
            for m in models
        ]
    else:
        available = [
            getattr(m, "model", str(m))
            for m in getattr(models, "models", [])
        ]

    for name in available:
        name_clean = name.strip()
        if (
            model_name == name_clean
            or model_name.split(":")[0] == name_clean.split(":")[0]
        ):
            logger.info("[Ollama] Model '%s' is ready", model_name)
            return True

    logger.info(
        "[Ollama] Model '%s' not found locally -- pulling now...", model_name
    )
    try:
        for _ in client.pull(model_name, stream=True):
            pass
        logger.info("[Ollama] Successfully pulled '%s'", model_name)
        return True
    except Exception as e:
        logger.error("[Ollama] Failed to pull model '%s': %s", model_name, e)
        return False


def auto_configure_fallback_ai() -> None:
    from dotenv import load_dotenv

    load_dotenv(settings.project_root / ".env", override=True)

    grok_key = os.environ.get("GROK_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()

    chosen_provider = None
    chosen_model = None

    if grok_key:
        chosen_provider = "grok"
        chosen_model = os.environ.get("GROK_MODEL", "gpt-oss-120b").strip()
    elif gemini_key:
        chosen_provider = "gemini"
        chosen_model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash").strip()

    if chosen_provider and chosen_model:
        os.environ["DEFAULT_LLM_PROVIDER"] = chosen_provider
        settings.default_llm_provider = chosen_provider
        logger.warning(
            "[AI Auto-Detect] Ollama is not running/installed. "
            "Found active API key for %s in .env. Auto-switched default AI to: %s (Model: %s)",
            chosen_provider.upper(),
            chosen_provider.upper(),
            chosen_model,
        )
        print(
            f"\n======================================================================\n"
            f" [AI Auto-Detect] Ollama is offline or not installed.\n"
            f" Auto-selected default AI: {chosen_provider.upper()} (Model: {chosen_model})\n"
            f" using credentials found in your .env configuration.\n"
            f"======================================================================\n",
            flush=True,
        )
    else:
        logger.warning(
            "[AI Auto-Detect] Ollama is unavailable and no alternative API keys "
            "found in .env. Please configure an API key in Dashboard -> AI Settings."
        )
