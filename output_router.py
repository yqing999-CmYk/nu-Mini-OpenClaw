import json
from datetime import datetime, timezone
from pathlib import Path


class OutputRouter:
    """
    Routes agent output to the correct destination (CLI, Telegram, log).
    Telegram bot is injected in Phase 5; until then send_telegram is a no-op.
    """

    def __init__(self, config: dict):
        log_cfg = config.get("logging", {})
        self._enabled = log_cfg.get("enabled", True)
        log_dir = Path(log_cfg.get("dir", "logs"))
        log_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_path = log_dir / f"session_{ts}.jsonl"
        self._bot = None  # injected in Phase 5

    # ------------------------------------------------------------------
    # Telegram bot injection (Phase 5)
    # ------------------------------------------------------------------
    def set_telegram_bot(self, bot) -> None:
        self._bot = bot

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def log_message(self, role: str, content: str, origin: str) -> None:
        if not self._enabled:
            return
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "content": content,
            "origin": origin,
        }
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # Telegram send (Phase 5)
    # ------------------------------------------------------------------
    async def send_telegram(self, text: str, chat_id: int) -> None:
        if self._bot is None:
            return
        limit = 4096
        for i in range(0, len(text), limit):
            await self._bot.send_message(chat_id=chat_id, text=text[i : i + limit])
