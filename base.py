from abc import ABC, abstractmethod
from typing import AsyncGenerator


class LLMClient(ABC):
    """Abstract base for all LLM backends."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> dict:
        """
        Send messages and return a full response dict:
          {content: str, tool_calls: list, usage: {prompt_tokens, completion_tokens}}
        """
        ...

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Yield text chunks as they arrive.
        Default implementation wraps chat() as a single chunk.
        Override in subclasses for real streaming.
        """
        result = await self.chat(messages, tools)
        yield result.get("content", "")

    def set_model(self, model: str) -> None:
        pass
