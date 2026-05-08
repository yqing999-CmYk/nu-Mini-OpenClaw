"""
Skill manager — loads, executes, and installs agent skills.

Skill formats
─────────────
  <name>.skill.md   Prompt-based skill. YAML frontmatter describes the skill;
                    the body is the system-prompt injected into a focused LLM call.
  <name>.skill.py   Code-based skill. Must expose async def run(**kwargs) -> str.
                    A YAML docstring at the top provides name/description metadata.
"""

import importlib.util
import inspect
import re
from pathlib import Path

import httpx
import yaml

from ..tools.registry import ToolRegistry


class SkillManager:

    def __init__(self, skills_dir: Path, registry_url: str = ""):
        self._dir = skills_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._registry_url = registry_url

    # ------------------------------------------------------------------ #
    # List / metadata
    # ------------------------------------------------------------------ #

    def list_local(self) -> list[dict]:
        skills: list[dict] = []
        for f in sorted(self._dir.iterdir()):
            if f.name.endswith(".skill.md") or f.name.endswith(".skill.py"):
                meta = self._parse_meta(f)
                if meta:
                    skills.append(meta)
        return skills

    def _parse_meta(self, path: Path) -> dict | None:
        try:
            content = path.read_text(encoding="utf-8")
            if path.name.endswith(".skill.md"):
                fm = _extract_frontmatter(content)
                return {
                    "name": fm.get("name", _stem(path)),
                    "description": fm.get("description", ""),
                    "version": str(fm.get("version", "")),
                    "type": "md",
                    "file": path.name,
                }
            else:  # .skill.py
                doc = _extract_py_docstring(content) or ""
                meta = yaml.safe_load(doc) if doc.strip() else {}
                return {
                    "name": meta.get("name", _stem(path)),
                    "description": meta.get("description", ""),
                    "version": str(meta.get("version", "")),
                    "type": "py",
                    "file": path.name,
                }
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Load (full content for execution)
    # ------------------------------------------------------------------ #

    def load(self, name: str) -> dict | None:
        """Return a skill dict ready for execution, or None if not found."""
        for filename in (f"{name}.skill.md", f"{name}.skill.py"):
            path = self._dir / filename
            if path.exists():
                return self._load_file(path)
        # Fuzzy: any file whose stem starts with the name
        for path in sorted(self._dir.iterdir()):
            if _stem(path) == name:
                return self._load_file(path)
        return None

    def _load_file(self, path: Path) -> dict:
        content = path.read_text(encoding="utf-8")
        if path.name.endswith(".skill.md"):
            fm = _extract_frontmatter(content)
            body = _strip_frontmatter(content).strip()
            return {
                "name": fm.get("name", _stem(path)),
                "description": fm.get("description", ""),
                "args_schema": fm.get("args", {}),
                "type": "md",
                "instructions": body,
            }
        else:
            return {
                "name": _stem(path),
                "type": "py",
                "path": path,
            }

    # ------------------------------------------------------------------ #
    # Execute
    # ------------------------------------------------------------------ #

    async def execute(self, skill: dict, args: dict, llm, workspace: Path) -> str:
        if skill["type"] == "md":
            return await self._exec_md(skill, args, llm)
        return await self._exec_py(skill, args, workspace)

    async def _exec_md(self, skill: dict, args: dict, llm) -> str:
        args_text = (
            "\n".join(f"  {k}: {v}" for k, v in args.items())
            if args else "  (no arguments provided)"
        )
        result = await llm.chat([
            {"role": "system", "content": skill["instructions"]},
            {"role": "user", "content": f"Execute with arguments:\n{args_text}"},
        ])
        return result.get("content", "")

    async def _exec_py(self, skill: dict, args: dict, workspace: Path) -> str:
        path: Path = skill["path"]
        # Load the module from file each time so edits are reflected immediately
        spec = importlib.util.spec_from_file_location(f"skill_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        run_fn = getattr(mod, "run", None)
        if run_fn is None:
            return f"Error: '{path.name}' has no 'run' function."
        try:
            result = run_fn(workspace=workspace, **args)
            if inspect.isawaitable(result):
                result = await result
            return str(result)
        except Exception as e:
            return f"Error running skill '{skill['name']}': {e}"

    # ------------------------------------------------------------------ #
    # Install from URL
    # ------------------------------------------------------------------ #

    async def install_from_url(self, url: str) -> str:
        headers = {"User-Agent": "nuMiniOpenClaw/1.0"}
        try:
            async with httpx.AsyncClient(
                headers=headers, timeout=20, follow_redirects=True
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
        except Exception as e:
            return f"Error downloading skill: {e}"

        # Derive filename from URL; ensure it has a skill extension
        url_clean = url.split("?")[0].rstrip("/")
        filename = url_clean.rsplit("/", 1)[-1]
        if not (filename.endswith(".skill.md") or filename.endswith(".skill.py")):
            # Keep the original extension but add .skill before it
            stem, ext = (filename.rsplit(".", 1) if "." in filename else (filename, ""))
            filename = f"{stem}.skill.{ext}" if ext in ("md", "py") else f"{filename}.skill.md"

        dest = self._dir / filename
        dest.write_text(resp.text, encoding="utf-8")
        return f"Skill installed as '{dest.name}'."

    # ------------------------------------------------------------------ #
    # Register LLM-callable tools
    # ------------------------------------------------------------------ #

    def register_tools(
        self, registry: ToolRegistry, llm, workspace: Path
    ) -> None:
        mgr = self

        # ── call_skill ──────────────────────────────────────────────── #
        async def call_skill(name: str, args: dict | None = None) -> str:
            skill = mgr.load(name)
            if skill is None:
                installed = [s["name"] for s in mgr.list_local()]
                hint = (
                    f"Installed: {', '.join(installed)}"
                    if installed else "No skills installed yet."
                )
                return f"Skill '{name}' not found. {hint}"
            return await mgr.execute(skill, args or {}, llm, workspace)

        registry.register(
            {
                "type": "function",
                "function": {
                    "name": "call_skill",
                    "description": (
                        "Invoke an installed skill by name. "
                        "Prompt-based skills run a focused LLM sub-task; "
                        "code-based skills execute Python."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Skill name (without extension).",
                            },
                            "args": {
                                "type": "object",
                                "description": "Key-value arguments passed to the skill.",
                            },
                        },
                        "required": ["name"],
                    },
                },
            },
            call_skill,
        )

        # ── install_skill ───────────────────────────────────────────── #
        async def install_skill(url: str) -> str:
            return await mgr.install_from_url(url)

        registry.register(
            {
                "type": "function",
                "function": {
                    "name": "install_skill",
                    "description": (
                        "Download and install a skill from a URL. "
                        "The URL should point to a .skill.md or .skill.py file."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "Direct URL to the skill file.",
                            }
                        },
                        "required": ["url"],
                    },
                },
            },
            install_skill,
        )


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _stem(path: Path) -> str:
    """Return skill name: strip both .skill and the final extension."""
    name = path.stem  # removes last suffix
    if name.endswith(".skill"):
        name = name[: -len(".skill")]
    return name


def _extract_frontmatter(content: str) -> dict:
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    return yaml.safe_load(content[3:end]) or {}


def _strip_frontmatter(content: str) -> str:
    if not content.startswith("---"):
        return content
    end = content.find("\n---", 3)
    return content[end + 4:] if end != -1 else content


def _extract_py_docstring(content: str) -> str | None:
    m = re.search(r'"""(.*?)"""', content, re.DOTALL)
    return m.group(1).strip() if m else None
