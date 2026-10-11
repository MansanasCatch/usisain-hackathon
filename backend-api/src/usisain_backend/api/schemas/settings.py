from pydantic import BaseModel


class UpdateAISettingsRequest(BaseModel):
    default_provider: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    grok_api_key: str | None = None
    grok_model: str | None = None
    ollama_model: str | None = None
    ollama_vision_model: str | None = None


class TestKeyRequest(BaseModel):
    provider: str
    api_key: str | None = None


class SwitchModelRequest(BaseModel):
    model: str


class SwitchProviderRequest(BaseModel):
    provider: str


class SwitchGeminiRequest(BaseModel):
    model: str = ""


class SwitchGrokRequest(BaseModel):
    model: str = ""
