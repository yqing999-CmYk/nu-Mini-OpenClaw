# nuMiniOpenClaw

A lightweight, local-first personal AI agent framework. Runs as a single Python process with a CLI, an optional Telegram bot, and a job scheduler — all sharing one event loop and one agent instance.

---

## How it works

```
main.py
  ├── Agent          — loads agent.md + user.md + memory.md, runs tool-calling turns
  ├── Scheduler      — APScheduler (cron / interval / startup), persists to schedules.json
  ├── Telegram bot   — python-telegram-bot v20+, polls in the background
  └── CLI            — prompt_toolkit interactive loop (foreground)
```

**Turn flow**

1. User sends a message (CLI or Telegram).
2. `Agent.run_turn()` appends it to that channel's `Context`, then calls the LLM.
3. If the LLM responds with tool calls, the agent executes them and loops back.
4. When the LLM returns plain text, the response is sent to the user and logged.

**Scheduled jobs**

Jobs fire via APScheduler and run through `Agent.run_one_shot()` — a throw-away context that never pollutes the interactive conversation. If the job was created from Telegram it pushes the result back to that chat.

**Context auto-summarize**

When a context's token count crosses `summarize_threshold` (default 24 000), the oldest turns are summarised into a two-message pair and the raw history is replaced. Configurable via `config.yaml`.

**Memory**

`memory.md` at the project root is re-read on every LLM call and included in the system prompt. The agent can update it with the `update_file` tool, making facts persist across sessions.

**Skills**

`.skill.md` — prompt-based: runs a focused LLM sub-call using the skill's instructions as the system prompt.  
`.skill.py` — code-based: Python module with `async def run(**kwargs)` called directly.  
Installed to `core/skills/installed/`. Accessible via the `call_skill` tool or `/install <url>`.

**Tools available to the agent**

| Tool | Description |
|---|---|
| `list_files` | List directory contents |
| `read_file` | Read a text file |
| `create_file` | Create a new file |
| `update_file` | Overwrite / upsert a file |
| `delete_file` | Delete a file |
| `run_shell` | Run a shell command (soft-sandboxed) |
| `web_search` | DuckDuckGo search, returns top results |
| `web_fetch` | Fetch and strip a web page to text |
| `read_image` | Describe a local image via the vision model |
| `run_python` | Execute a Python snippet, return output |
| `run_js` | Execute a Node.js snippet, return output |
| `call_skill` | Invoke an installed skill |
| `install_skill` | Download and install a skill from a URL |

---

## Setup

### 1. Clone and install

```bash
git clone <repo-url> nuMiniOpenClaw
cd nuMiniOpenClaw
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env`:

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...   # optional
TELEGRAM_BOT_TOKEN=...         # optional
```

### 3. Edit config.yaml

Key settings:

```yaml
llm:
  provider: openai              # openai | anthropic | openrouter | google
  model: gpt-4o

context:
  strategy: summarize
  max_tokens: 32000
  summarize_threshold: 24000

telegram:
  enabled: false                # set true to activate the bot
  allowed_ids: []               # add your Telegram numeric user ID
```

### 4. Personalise the agent (optional)

- `agent.md` — agent name, role, personality, and instructions
- `user.md` — your profile, preferences, and goals
- `memory.md` — persistent facts the agent should always remember (created by the agent or by hand)

---

## How to run

```bash
python main.py
```

The agent starts, loads schedules, optionally starts the Telegram bot, then opens the CLI prompt.

```
Nova is ready. Type /help for commands.

You:
```

### CLI commands

```
/help                              Show all commands
/clear                             Clear conversation context
/history [n]                       Show last n turns (default 10)
/persona                           Show agent.md
/user                              Show user.md
/cost                              Show total tokens used this session
/model <name>                      Switch model mid-session (e.g. gpt-4o-mini)
/provider <name>                   Switch provider (openai|anthropic|openrouter|google)
/workspace                         Show workspace file tree
/skills                            List installed skills
/install <url>                     Install a skill from a URL
/plan <goal>                       Decompose a goal into steps, confirm, then execute

/schedule list
/schedule add cron "*/5 * * * *" "summarise new files"
/schedule add loop 5m "check weather"
/schedule add start "morning brief"
/schedule remove <id>
/schedule enable <id>
/schedule disable <id>

/loop 30s "ping"                   Session-only loop (not saved)
/loop list
/loop stop <id>

/exit
```

---
---

## Deployment options

### Option A — Run directly on a server (simplest)

```bash
# Install dependencies
pip install -r requirements.txt

# Run in a persistent session with tmux or screen
tmux new -s agent
python main.py
# Ctrl-B D  to detach

# Or with nohup
nohup python main.py > logs/agent.log 2>&1 &
```

### Option B — systemd service (Linux)

Create `/etc/systemd/system/numiniopenclaw.service`:

```ini
[Unit]
Description=nuMiniOpenClaw AI Agent
After=network.target

[Service]
User=youruser
WorkingDirectory=/home/youruser/nuMiniOpenClaw
ExecStart=/home/youruser/nuMiniOpenClaw/.venv/bin/python main.py
Restart=on-failure
RestartSec=10
EnvironmentFile=/home/youruser/nuMiniOpenClaw/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable numiniopenclaw
sudo systemctl start numiniopenclaw
sudo systemctl status numiniopenclaw
```

Note: the interactive CLI prompt is not usable in this mode. The agent is reachable through Telegram and scheduled jobs only. Disable the CLI loop or point stdout to a log file.

### Option C — Docker

#### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

#### Build and run

```bash
docker build -t numiniopenclaw .

docker run -d \
  --name agent \
  --restart unless-stopped \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/workspace:/app/workspace \
  -v $(pwd)/schedules.json:/app/schedules.json \
  -v $(pwd)/memory.md:/app/memory.md \
  --env-file .env \
  numiniopenclaw
```

Volumes keep logs, workspace files, schedules, and memory persistent across container restarts.


### Option D — Cloud VM (AWS / GCP / Azure / DigitalOcean)

1. Provision an Ubuntu 22.04 VM (1 vCPU / 1 GB RAM is enough for most workloads).
2. SSH in, clone the repo, follow the **systemd** or **Docker** instructions above.
3. The agent communicates outbound only (Telegram polling, OpenAI API). No inbound port needs to be opened.

---

## Future update options (Phase 7+)

| Feature | Description |
|---|---|
| **Hard Docker sandbox** | Run `run_python` / `run_shell` inside an isolated container instead of the host process. Prevents the agent from accessing host files or network outside the sandbox. |
| **Remote skill registry** | A hosted index of `.skill.md` / `.skill.py` files. `/install <name>` resolves to the registry URL automatically instead of requiring a raw URL. |
| **Telegram inline buttons** | Schedule management via Telegram inline keyboards — tap to enable, disable, or remove a job without typing commands. |
| **Streaming to Telegram** | Stream LLM tokens to Telegram by editing the bot's message in-place as tokens arrive, rather than waiting for the full response. |
