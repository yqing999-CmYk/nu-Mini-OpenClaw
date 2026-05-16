import asyncio
from pathlib import Path

from .registry import ToolRegistry

# Commands that are hard-blocked in soft sandbox mode
_BLOCKED = {
    # Unix
    "rm", "rmdir", "mkfs", "dd", "shred", "wipefs",
    "shutdown", "reboot", "poweroff", "halt",
    # Windows
    "del", "rd", "format", "cipher",
}

TIMEOUT_SECONDS = 30


def register(registry: ToolRegistry, workspace: Path, config: dict | None = None) -> None:
    """
    Register shell command tool.

    If config has sandbox.mode="docker", uses Docker sandbox.
    Otherwise uses soft sandbox with command blocklist.
    """
    sandbox_config = (config or {}).get("sandbox", {})
    sandbox_mode = sandbox_config.get("mode", "soft")

    if sandbox_mode == "docker":
        # Use Docker sandbox
        from .docker_sandbox import DockerSandbox

        docker_image = sandbox_config.get("docker_image", "python:3.11")
        docker_timeout = sandbox_config.get("docker_timeout", 30)
        sandbox = DockerSandbox(workspace, docker_image, docker_timeout)

        async def run_shell(command: str) -> str:
            return await sandbox.run(command)

    else:
        # Use soft sandbox (default)
        async def run_shell(command: str) -> str:
            # Soft-sandbox check: block known destructive commands
            first_token = command.strip().split()[0].lower() if command.strip() else ""
            # Strip leading path prefix (e.g. /bin/rm → rm)
            first_token = first_token.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            if first_token in _BLOCKED:
                return (
                    f"Error: '{first_token}' is blocked. "
                    "Use delete_file for removing files inside the workspace."
                )

            try:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    cwd=str(workspace),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                return f"Error: command timed out after {TIMEOUT_SECONDS}s."
            except Exception as e:
                return f"Error launching command: {e}"

            out = stdout.decode("utf-8", errors="replace").strip()
            err = stderr.decode("utf-8", errors="replace").strip()

            parts: list[str] = []
            if out:
                parts.append(out)
            if err:
                parts.append(f"[stderr]\n{err}")
            if proc.returncode != 0:
                parts.append(f"[exit code {proc.returncode}]")

            return "\n".join(parts) if parts else "(no output)"

    desc = (
        "Execute a shell command in a Docker container (isolated sandbox)."
        if sandbox_mode == "docker"
        else "Execute a shell command inside the workspace directory (soft sandbox)."
    )

    registry.register(
        {
            "type": "function",
            "function": {
                "name": "run_shell",
                "description": (
                    f"{desc} "
                    "Returns stdout, stderr, and exit code."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Shell command to execute.",
                        }
                    },
                    "required": ["command"],
                },
            },
        },
        run_shell,
    )
