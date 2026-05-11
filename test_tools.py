"""Phase 2 tool tests — run with: python tests/test_tools.py"""
import asyncio
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.tools.registry import ToolRegistry
from core.tools import file_tools, shell_tools


# ------------------------------------------------------------------ #
# File tools
# ------------------------------------------------------------------ #

def test_file_tools():
    async def _run():
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            reg = ToolRegistry()
            file_tools.register(reg, ws)

            # create_file
            r = await reg.call("create_file", {"path": "hello.txt", "content": "Hello!"})
            assert "Created" in r, r

            # create_file again → error
            r = await reg.call("create_file", {"path": "hello.txt", "content": "dup"})
            assert "already exists" in r, r

            # read_file
            r = await reg.call("read_file", {"path": "hello.txt"})
            assert r == "Hello!", r

            # update_file (overwrite)
            r = await reg.call("update_file", {"path": "hello.txt", "content": "Updated"})
            assert "Updated" in r, r
            r = await reg.call("read_file", {"path": "hello.txt"})
            assert r == "Updated", r

            # update_file (upsert — new file)
            r = await reg.call("update_file", {"path": "new.txt", "content": "New"})
            assert "Created" in r, r

            # list_files
            r = await reg.call("list_files", {})
            assert "hello.txt" in r, r
            assert "new.txt" in r, r

            # delete_file
            r = await reg.call("delete_file", {"path": "hello.txt"})
            assert "Deleted" in r, r
            r = await reg.call("read_file", {"path": "hello.txt"})
            assert "does not exist" in r, r

            # path traversal → error
            r = await reg.call("read_file", {"path": "../../etc/passwd"})
            assert "outside" in r.lower() or "Error" in r, r

    asyncio.run(_run())
    print("  file_tools:     PASS")


# ------------------------------------------------------------------ #
# Shell tool
# ------------------------------------------------------------------ #

def test_shell_tool():
    async def _run():
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            reg = ToolRegistry()
            shell_tools.register(reg, ws)

            # basic echo
            r = await reg.call("run_shell", {"command": "echo hello"})
            assert "hello" in r, r

            # blocked command
            r = await reg.call("run_shell", {"command": "rm -rf ."})
            assert "blocked" in r.lower(), r

            r = await reg.call("run_shell", {"command": "del /f test"})
            assert "blocked" in r.lower(), r

    asyncio.run(_run())
    print("  shell_tool:     PASS")


# ------------------------------------------------------------------ #
# Registry error handling
# ------------------------------------------------------------------ #

def test_registry_unknown_tool():
    async def _run():
        reg = ToolRegistry()
        r = await reg.call("nonexistent", {})
        assert "unknown tool" in r, r

    asyncio.run(_run())
    print("  registry:       PASS")


if __name__ == "__main__":
    print("Running Phase 2 tool tests...")
    test_file_tools()
    test_shell_tool()
    test_registry_unknown_tool()
    print("All tests passed.")
