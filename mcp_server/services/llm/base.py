"""base.py — common interface both LLM providers implement, so the tools
that call them (steps 1, 3, 4, 5) don't care which one is active."""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str, image_path: str = None, max_tokens: int | None = None) -> str:
        """Return a plain-text completion. Implementations should raise on
        failure rather than silently returning an empty string — callers
        decide how to handle unavailability."""
        raise NotImplementedError

