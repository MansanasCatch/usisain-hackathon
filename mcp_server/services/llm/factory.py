"""factory.py — unified LLM provider factory with smooth Ollama fallback.

Guarantees:
1. Ollama is always the default provider.
2. Gemini and Grok are optional alternatives.
3. If Gemini or Grok is requested but has no API key configured, or encounters
   an error during execution (quota, network, invalid key, timeout), the system
   smoothly falls back to Ollama so the analysis pipeline never dead-ends.
"""

import os
import logging
from .base import LLMProvider
from .ollama_client import OllamaProvider, is_ollama_available

logger = logging.getLogger(__name__)


class FallbackWrapper(LLMProvider):
    """Wraps a primary cloud provider (Gemini or Grok) and delegates to Ollama
    if the primary provider fails at runtime, or to the alternate cloud provider
    if Ollama is unavailable or not installed."""

    def __init__(self, primary: LLMProvider, primary_name: str):
        self.primary = primary
        self.primary_name = primary_name
        self.name = primary_name
        self.fallback = OllamaProvider()

    async def complete(self, system: str, user: str, image_path: str = None, max_tokens: int | None = None) -> str:
        try:
            return await self.primary.complete(system, user, image_path=image_path, max_tokens=max_tokens)
        except Exception as exc:
            logger.warning(
                "Primary provider '%s' failed (%s) — checking available fallbacks...",
                self.primary_name,
                exc,
            )
            # If Ollama is available, use local Ollama
            if is_ollama_available():
                return await self.fallback.complete(system, user, image_path=image_path, max_tokens=max_tokens)

            # If Ollama is failing or not installed, check if the other cloud provider has a key
            from .grok_client import GrokProvider, KEY_POOL as GROK_POOL
            from .gemini_client import GeminiProvider, KEY_POOL as GEMINI_POOL

            if self.primary_name != "grok" and GROK_POOL.has_keys():
                logger.info("Ollama is unavailable — smoothly falling back to Grok.")
                try:
                    return await GrokProvider().complete(system, user, image_path=image_path, max_tokens=max_tokens)
                except Exception as grok_err:
                    logger.warning("Grok fallback also failed: %s", grok_err)
            elif self.primary_name != "gemini" and GEMINI_POOL.has_keys():
                logger.info("Ollama is unavailable — smoothly falling back to Gemini.")
                try:
                    return await GeminiProvider().complete(system, user, image_path=image_path, max_tokens=max_tokens)
                except Exception as gem_err:
                    logger.warning("Gemini fallback also failed: %s", gem_err)

            # Fall back to Ollama anyway (will record error)
            return await self.fallback.complete(system, user, image_path=image_path, max_tokens=max_tokens)


def get_provider(preference: str | None = None) -> LLMProvider:
    """Return the requested LLM provider with automatic fallback.

    If Ollama is default/requested but is failing or not installed, automatically
    detects which cloud AI model in .env has an active API key (Grok or Gemini)
    and uses it as the default AI.
    """
    selected = (preference or os.environ.get("DEFAULT_LLM_PROVIDER") or "ollama").strip().lower()

    from .grok_client import GrokProvider, KEY_POOL as GROK_POOL
    from .gemini_client import GeminiProvider, KEY_POOL as GEMINI_POOL

    if selected == "gemini":
        if GEMINI_POOL.has_keys():
            try:
                return FallbackWrapper(GeminiProvider(), "gemini")
            except Exception as e:
                logger.warning("Could not initialize Gemini provider (%s) — checking alternatives.", e)
        else:
            logger.info("Gemini selected but no GEMINI_API_KEY set — checking alternatives.")

    elif selected == "grok":
        if GROK_POOL.has_keys():
            try:
                return FallbackWrapper(GrokProvider(), "grok")
            except Exception as e:
                logger.warning("Could not initialize Grok provider (%s) — checking alternatives.", e)
        else:
            logger.info("Grok selected but no GROK_API_KEY set — checking alternatives.")

    # If Ollama was requested (or if the selected cloud provider had no key):
    # 1. If Ollama is running and healthy, use Ollama (local default)
    if is_ollama_available():
        return OllamaProvider()

    # 2. Ollama is failing or not installed: look for an AI model in .env that has an API key!
    if GROK_POOL.has_keys():
        logger.info("[Auto-Detect] Ollama is unavailable. Auto-selected Grok (gpt-oss-120b) with key from .env.")
        try:
            return FallbackWrapper(GrokProvider(), "grok")
        except Exception:
            pass
    elif GEMINI_POOL.has_keys():
        logger.info("[Auto-Detect] Ollama is unavailable. Auto-selected Gemini with key from .env.")
        try:
            return FallbackWrapper(GeminiProvider(), "gemini")
        except Exception:
            pass

    # 3. Default fallback
    return OllamaProvider()
