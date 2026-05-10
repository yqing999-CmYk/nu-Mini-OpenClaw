"""
Anthropic client — translates the shared OpenAI-style interface to
the Anthropic Messages API (tool use included).
"""

import json

from anthropic import AsyncAnthropic

from .base import LLMClient


class _FunctionCall:
    __slots__ = ("name", "arguments")

    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class _ToolCall:
    __slots__ = ("id", "function")

    def __init__(self, call_id: str, name: str, arguments: str):
        self.id = call_id
        self.function = _FunctionCall(name, arguments)


class AnthropicClient(LLMClient):

    def __init__(self, config: dict):
        cfg = config.get("llm", {})
        self._client = AsyncAnthropic(api_key=cfg.get("api_key", ""))
        self._model: str = cfg.get("model", "claude-opus-4-7")
        self._max_tokens: int = cfg.get("max_tokens", 4096)
        self._temperature: float = cfg.get("temperature", 0.7)

    def set_model(self, model: str) -> None:
        self._model = model

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> dict:
        # Split system message out (Anthropic takes it as a top-level param)
        system = ""
        conv: list[dict] = []
        for m in messages:
            if m["role"] == "system":
                content = m.get("content") or ""
                if isinstance(content, list):
                    content = " ".join(
                        b.get("text", "") for b in content if b.get("type") == "text"
                    )
                system = content
            else:
                conv.append(m)

        # Convert OpenAI-format messages to Anthropic format
        anthropic_msgs: list[dict] = []
        for m in conv:
            role = m["role"]

            if role == "tool":
                # Tool result → append as user turn with tool_result block
                anthropic_msgs.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m["tool_call_id"],
                        "content": m.get("content", ""),
                    }],
                })

            elif role == "assistant" and m.get("tool_calls"):
                # Tool call decision → assistant turn with tool_use blocks
                content_blocks = []
                if m.get("content"):
                    content_blocks.append({"type": "text", "text": m["content"]})
                for tc in m["tool_calls"]:
                    fn = tc["function"]
                    try:
                        inp = json.loads(fn["arguments"])
                    except (json.JSONDecodeError, TypeError):
                        inp = {}
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": fn["name"],
                        "input": inp,
                    })
                anthropic_msgs.append({"role": "assistant", "content": content_blocks})

            else:
                anthropic_msgs.append(m)

        # Convert tools schema (OpenAI → Anthropic)
        anthropic_tools = None
        if tools:
            anthropic_tools = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"].get("parameters", {}),
                }
                for t in tools
            ]

        kwargs: dict = dict(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=anthropic_msgs,
        )
        if system:
            kwargs["system"] = system
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        resp = await self._client.messages.create(**kwargs)

        content_text = ""
        tool_calls: list[_ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                content_text = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    _ToolCall(block.id, block.name, json.dumps(block.input))
                )

        usage = resp.usage
        return {
            "content": content_text,
            "tool_calls": tool_calls,
            "usage": {
                "prompt_tokens": getattr(usage, "input_tokens", 0),
                "completion_tokens": getattr(usage, "output_tokens", 0),
            },
        }
