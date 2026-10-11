from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        image_path: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        raise NotImplementedError


LLMProvider = BaseLLMProvider
