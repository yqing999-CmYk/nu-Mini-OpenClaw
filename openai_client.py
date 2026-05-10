from typing import AsyncGenerator

from openai import AsyncOpenAI

from .base import LLMClient


class OpenAIClient(LLMClient):

    def __init__(self, config: dict):
        cfg = config.get("llm", {})
        self._client = AsyncOpenAI(api_key=cfg.get("api_key", ""))
        self._model: str = cfg.get("model", "gpt-4o")
        self._temperature: float = cfg.get("temperature", 0.7)
        self._max_tokens: int = cfg.get("max_tokens", 4096)

    def set_model(self, model: str) -> None:
        self._model = model

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> dict:
        kwargs: dict = dict(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp = await self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        usage = resp.usage

        return {
            "content": choice.message.content or "",
            "tool_calls": choice.message.tool_calls or [],
            "usage": {
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
            },
        }

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        kwargs: dict = dict(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            stream=True,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = await self._client.chat.completions.create(**kwargs)
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content
