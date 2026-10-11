import logging
import os

from .base import LLMProvider
from .ollama_client import OllamaProvider, is_ollama_available

logger = logging.getLogger(__name__)


class FallbackWrapper(LLMProvider):
    def __init__(self, primary: LLMProvider, primary_name: str):
        self.primary = primary
        self.primary_name = primary_name
        self.name = primary_name
        self.fallback = OllamaProvider()

    async def complete(
        self, system: str, user: str, image_path: str = None, max_tokens: int | None = None
    ) -> str:
        try:
            return await self.primary.complete(
                system, user, image_path=image_path, max_tokens=max_tokens
            )
        except Exception as exc:
            logger.warning(
                "Primary provider '%s' failed (%s) — checking available fallbacks...",
                self.primary_name,
                exc,
            )
            if is_ollama_available():
                return await self.fallback.complete(
                    system, user, image_path=image_path, max_tokens=max_tokens
                )
            from .gemini_client import KEY_POOL as GEMINI_POOL
            from .gemini_client import GeminiProvider
            from .grok_client import KEY_POOL as GROK_POOL
            from .grok_client import GrokProvider

            if self.primary_name != "grok" and GROK_POOL.has_keys():
                logger.info("Ollama is unavailable — smoothly falling back to Grok.")
                try:
                    return await GrokProvider().complete(
                        system, user, image_path=image_path, max_tokens=max_tokens
                    )
                except Exception as grok_err:
                    logger.warning("Grok fallback also failed: %s", grok_err)
            elif self.primary_name != "gemini" and GEMINI_POOL.has_keys():
                logger.info("Ollama is unavailable — smoothly falling back to Gemini.")
                try:
                    return await GeminiProvider().complete(
                        system, user, image_path=image_path, max_tokens=max_tokens
                    )
                except Exception as gem_err:
                    logger.warning("Gemini fallback also failed: %s", gem_err)
            return await self.fallback.complete(
                system, user, image_path=image_path, max_tokens=max_tokens
            )


FallbackProvider = FallbackWrapper


def get_provider(preference: str | None = None) -> LLMProvider:
    selected = (preference or os.environ.get("DEFAULT_LLM_PROVIDER") or "ollama").strip().lower()
    from .gemini_client import KEY_POOL as GEMINI_POOL
    from .gemini_client import GeminiProvider
    from .grok_client import KEY_POOL as GROK_POOL
    from .grok_client import GrokProvider

    if selected == "gemini":
        if GEMINI_POOL.has_keys():
            try:
                return FallbackWrapper(GeminiProvider(), "gemini")
            except Exception as e:
                logger.warning(
                    "Could not initialize Gemini provider (%s) — checking alternatives.", e
                )
        else:
            logger.info("Gemini selected but no GEMINI_API_KEY set — checking alternatives.")
    elif selected == "grok":
        if GROK_POOL.has_keys():
            try:
                return FallbackWrapper(GrokProvider(), "grok")
            except Exception as e:
                logger.warning(
                    "Could not initialize Grok provider (%s) — checking alternatives.", e
                )
        else:
            logger.info("Grok selected but no GROK_API_KEY set — checking alternatives.")
    if is_ollama_available():
        return OllamaProvider()
    if GROK_POOL.has_keys():
        logger.info(
            "[Auto-Detect] Ollama is unavailable. Auto-selected Grok (gpt-oss-120b) with key from .env."
        )
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
    return OllamaProvider()
