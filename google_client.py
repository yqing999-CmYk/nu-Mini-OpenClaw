"""
Google Generative AI client — stub.
Install google-generativeai and implement when needed.
"""

from .base import LLMClient


class GoogleClient(LLMClient):
    """Stub — implement with google-generativeai when needed."""

    def __init__(self, config: dict):
        cfg = config.get("llm", {})
        self._model: str = cfg.get("model", "gemini-1.5-pro")

    def set_model(self, model: str) -> None:
        self._model = model

    async def chat(self, messages, tools=None) -> dict:
        raise NotImplementedError(
            "Google client not yet implemented. "
            "Install google-generativeai and fill in google_client.py."
        )
