import json
from typing import Awaitable, Callable


class ToolRegistry:
    """
    Central registry for all agent tools.
    Tools are registered with an OpenAI-compatible JSON schema and an async callable.
    Phase 2 will register file, shell, and web tools here.
    """

    def __init__(self):
        self._tools: dict[str, dict] = {}

    def register(self, schema: dict, fn: Callable[..., Awaitable[str]]) -> None:
        """
        schema must follow the OpenAI tool schema format:
          {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
        """
        name = schema["function"]["name"]
        self._tools[name] = {"schema": schema, "fn": fn}

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def schemas(self) -> list[dict]:
        return [v["schema"] for v in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    async def call(self, name: str, arguments: str | dict) -> str:
        if name not in self._tools:
            return f"Error: unknown tool '{name}'"
        args = arguments if isinstance(arguments, dict) else json.loads(arguments or "{}")
        try:
            result = await self._tools[name]["fn"](**args)
            return str(result)
        except Exception as e:
            return f"Error executing '{name}': {e}"
