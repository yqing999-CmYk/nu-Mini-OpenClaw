"""Quick smoke tests for Phase 1 — run with: python tests/smoke_test.py"""
import asyncio
import sys
import os

# Run from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.context import Context
from core.tools.registry import ToolRegistry
from core.config import load_config


def test_context():
    ctx = Context({})
    ctx.add("user", "hello")
    ctx.add("assistant", "hi")
    assert len(ctx.get_messages()) == 2
    ctx.record_tokens(10, 5)
    assert ctx.total_tokens == 15
    ctx.clear()
    assert len(ctx.get_messages()) == 0
    print("  context:        PASS")


def test_tool_registry():
    async def _run():
        reg = ToolRegistry()
        schema = {
            "type": "function",
            "function": {
                "name": "echo",
                "description": "echo",
                "parameters": {
                    "type": "object",
                    "properties": {"msg": {"type": "string"}},
                    "required": ["msg"],
                },
            },
        }

        async def echo(msg: str) -> str:
            return msg

        reg.register(schema, echo)
        assert reg.schemas()[0]["function"]["name"] == "echo"
        result = await reg.call("echo", '{"msg": "hello"}')
        assert result == "hello", f"Expected 'hello', got '{result}'"
        unknown = await reg.call("does_not_exist", "{}")
        assert "unknown tool" in unknown
        print("  tool_registry:  PASS")

    asyncio.run(_run())


def test_load_config():
    cfg = load_config()
    assert "llm" in cfg
    assert "telegram" in cfg
    assert "logging" in cfg
    print("  load_config:    PASS")


if __name__ == "__main__":
    print("Running smoke tests...")
    test_context()
    test_tool_registry()
    test_load_config()
    print("All tests passed.")
