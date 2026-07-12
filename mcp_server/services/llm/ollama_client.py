"""ollama_client.py — local LLM provider via Ollama. This is the default
provider: fully offline, no API key, no data leaves the machine."""

import os
import ollama
from .base import LLMProvider

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


class OllamaProvider(LLMProvider):
    def __init__(self, model: str | None = None, host: str | None = None):
        self.model = model or OLLAMA_MODEL
        self.client = ollama.Client(host=host or OLLAMA_HOST)

    def complete(self, system: str, user: str) -> str:
        response = self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.message.content.strip()
