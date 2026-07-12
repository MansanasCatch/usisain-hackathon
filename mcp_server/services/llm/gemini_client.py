"""gemini_client.py — optional cloud LLM provider. Use this when you want
stronger reasoning than a local 7-8B model can reliably give (e.g. for
step 3's source-relevance explanations), at the cost of that content
leaving the machine. Get a free API key at https://aistudio.google.com/apikey"""

import os
from .base import LLMProvider

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or GEMINI_MODEL
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set — get one at https://aistudio.google.com/apikey")

    def complete(self, system: str, user: str) -> str:
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model, system_instruction=system)
        response = model.generate_content(user)
        return response.text.strip()


def get_provider(preference: str = "ollama") -> LLMProvider:
    """Factory: 'ollama' (default, local) or 'gemini' (cloud fallback).
    Falls back to Ollama automatically if Gemini isn't configured."""
    if preference == "gemini" and GEMINI_API_KEY:
        return GeminiProvider()
    from .ollama_client import OllamaProvider
    return OllamaProvider()
