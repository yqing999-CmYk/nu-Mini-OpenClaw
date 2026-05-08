class Context:
    """Holds the conversation message history for one channel (CLI or Telegram chat)."""

    def __init__(self, config: dict):
        self._messages: list[dict] = []
        self.total_tokens: int = 0

    def add(self, role: str, content) -> None:
        self._messages.append({"role": role, "content": content})

    def add_assistant_tool_calls(self, tool_calls: list[dict]) -> None:
        """Store an assistant turn that contains tool call decisions (no text content)."""
        self._messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls,
        })

    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        self._messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": content,
        })

    def get_messages(self) -> list[dict]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    def record_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.total_tokens += prompt_tokens + completion_tokens

    def replace_with_summary(self, summary_text: str, tail: list[dict]) -> None:
        """Replace history with a summary turn + the most recent tail turns."""
        self._messages = [
            {"role": "user", "content": "[Earlier conversation — summarized below]"},
            {"role": "assistant", "content": f"Summary of our earlier conversation:\n{summary_text}"},
        ] + tail
        self.total_tokens = 0
