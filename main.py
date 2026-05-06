"""
nuMiniOpenClaw — main entry point.

Phase 1: CLI only (prompt_toolkit).
Phase 4: Scheduler added.
Phase 5: Telegram bot added.
"""

import asyncio

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory

from core.agent import Agent
from core.config import load_config
from core.llm.openai_client import OpenAIClient
from core.output_router import OutputRouter

# ---------------------------------------------------------------------------
# Slash-command autocomplete list
# ---------------------------------------------------------------------------
SLASH_COMMANDS = [
    "/help", "/clear", "/history", "/model", "/provider",
    "/skills", "/install", "/persona", "/user", "/workspace",
    "/cost", "/plan", "/loop", "/schedule", "/exit",
]

HELP_TEXT = """
Commands (Phase 1):
  /help                    This help text
  /clear                   Clear conversation context
  /history [n]             Show last n turns (default 10)
  /persona                 Show agent.md content
  /user                    Show user.md content
  /cost                    Show token usage this session
  /model <name>            Switch LLM model mid-session

Coming in later phases:
  /workspace               Show workspace file tree          (Phase 2)
  /skills                  List installed skills              (Phase 3)
  /install <skill>         Download and install a skill       (Phase 3)
  /loop <interval> <task>  Session-only repeating task        (Phase 4)
  /schedule ...            Manage persistent scheduled jobs   (Phase 4)
  /plan <goal>             Decompose goal and execute steps   (Phase 6)

  /exit                    Quit
"""


# ---------------------------------------------------------------------------
# Slash-command handler
# ---------------------------------------------------------------------------

async def handle_slash_command(cmd: str, agent: Agent) -> bool:
    """Handle a /command string. Returns True if the session should exit."""
    parts = cmd.split(maxsplit=1)
    name = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    if name == "/exit":
        print("Goodbye.")
        return True

    elif name == "/help":
        print(HELP_TEXT)

    elif name == "/clear":
        agent.context.clear()
        print("Context cleared.")

    elif name == "/history":
        n = int(args) if args.isdigit() else 10
        msgs = agent.context.get_messages()
        shown = msgs[-(n * 2):]
        if not shown:
            print("(no history)")
        for msg in shown:
            role = msg.get("role", "?").capitalize()
            content = msg.get("content") or ""
            if isinstance(content, list):
                content = "[multimodal]"
            elif not isinstance(content, str):
                content = str(content)
            print(f"[{role}] {content[:300]}")

    elif name == "/persona":
        print(agent.agent_md or "(agent.md not found)")

    elif name == "/user":
        print(agent.user_md or "(user.md not found)")

    elif name == "/cost":
        print(f"Total tokens this session: {agent.context.total_tokens}")

    elif name == "/model":
        if args:
            agent.llm.set_model(args)
            print(f"Model switched to: {args}")
        else:
            print("Usage: /model <model-name>   e.g. /model gpt-4o-mini")

    else:
        print(f"Unknown command '{name}'. Type /help for the list.")

    return False


# ---------------------------------------------------------------------------
# CLI loop
# ---------------------------------------------------------------------------

async def cli_loop(agent: Agent) -> None:
    session: PromptSession = PromptSession(
        history=FileHistory(".cli_history"),
        auto_suggest=AutoSuggestFromHistory(),
        completer=WordCompleter(SLASH_COMMANDS, sentence=True),
        complete_while_typing=False,
    )

    print(f"\n{agent.name} is ready. Type /help for commands.\n")

    while True:
        try:
            user_input: str = await session.prompt_async("You: ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input.startswith("/"):
            should_exit = await handle_slash_command(user_input, agent)
            if should_exit:
                break
            continue

        response = await agent.run_turn(user_input, origin="cli")
        print(f"\n{agent.name}: {response}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    config = load_config()
    llm = OpenAIClient(config)
    router = OutputRouter(config)
    agent = Agent(config, llm, router)
    await agent.load()

    # Phase 4: start scheduler here
    # Phase 5: start Telegram bot here

    await cli_loop(agent)


if __name__ == "__main__":
    asyncio.run(main())
