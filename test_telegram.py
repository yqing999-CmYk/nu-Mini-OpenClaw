"""
Phase 5 tests — Telegram auth, handler logic, bot lifecycle.
Uses unittest.mock throughout; no real Telegram connection required.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------

def test_is_allowed_with_matching_id():
    from core.telegram.auth import is_allowed
    config = {"telegram": {"allowed_ids": [123456, 789]}}
    assert is_allowed(123456, config) is True


def test_is_allowed_with_non_matching_id():
    from core.telegram.auth import is_allowed
    config = {"telegram": {"allowed_ids": [111]}}
    assert is_allowed(999, config) is False


def test_is_allowed_empty_list_denies_all():
    from core.telegram.auth import is_allowed
    config = {"telegram": {"allowed_ids": []}}
    assert is_allowed(123456, config) is False


def test_is_allowed_missing_telegram_key():
    from core.telegram.auth import is_allowed
    assert is_allowed(123456, {}) is False


def test_is_allowed_string_ids_coerced():
    from core.telegram.auth import is_allowed
    config = {"telegram": {"allowed_ids": ["123456"]}}
    assert is_allowed(123456, config) is True


# ---------------------------------------------------------------------------
# _do_schedule (pure logic, no network)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_scheduler():
    s = MagicMock()
    s.list_jobs.return_value = []
    s.add_job.return_value = None
    s.remove_job.return_value = True
    s.enable_job.return_value = True
    s.disable_job.return_value = True
    return s


@pytest.mark.asyncio
async def test_do_schedule_list_empty(mock_scheduler):
    from core.telegram.handlers import _do_schedule
    result = await _do_schedule("list", mock_scheduler, "telegram", 42)
    assert "No scheduled jobs" in result


@pytest.mark.asyncio
async def test_do_schedule_add_loop(mock_scheduler):
    from core.telegram.handlers import _do_schedule
    result = await _do_schedule('add loop 5m "check weather"', mock_scheduler, "telegram", 42)
    assert "Interval job added" in result
    assert mock_scheduler.add_job.called


@pytest.mark.asyncio
async def test_do_schedule_add_cron(mock_scheduler):
    from core.telegram.handlers import _do_schedule
    result = await _do_schedule('add cron "*/5 * * * *" "ping"', mock_scheduler, "telegram", 42)
    assert "Cron job added" in result
    assert mock_scheduler.add_job.called


@pytest.mark.asyncio
async def test_do_schedule_add_start(mock_scheduler):
    from core.telegram.handlers import _do_schedule
    result = await _do_schedule('add start "init task"', mock_scheduler, "telegram", 42)
    assert "Startup job added" in result


@pytest.mark.asyncio
async def test_do_schedule_remove(mock_scheduler):
    from core.telegram.handlers import _do_schedule
    result = await _do_schedule("remove abc123", mock_scheduler, "telegram", 42)
    assert "removed" in result
    mock_scheduler.remove_job.assert_called_once_with("abc123")


@pytest.mark.asyncio
async def test_do_schedule_remove_not_found(mock_scheduler):
    mock_scheduler.remove_job.return_value = False
    from core.telegram.handlers import _do_schedule
    result = await _do_schedule("remove xyz", mock_scheduler, "telegram", 42)
    assert "No job" in result


@pytest.mark.asyncio
async def test_do_schedule_enable(mock_scheduler):
    from core.telegram.handlers import _do_schedule
    result = await _do_schedule("enable abc", mock_scheduler, "telegram", 42)
    assert "enabled" in result


@pytest.mark.asyncio
async def test_do_schedule_disable(mock_scheduler):
    from core.telegram.handlers import _do_schedule
    result = await _do_schedule("disable abc", mock_scheduler, "telegram", 42)
    assert "disabled" in result


@pytest.mark.asyncio
async def test_do_schedule_unknown_sub(mock_scheduler):
    from core.telegram.handlers import _do_schedule
    result = await _do_schedule("bogus", mock_scheduler, "telegram", 42)
    assert "Unknown sub-command" in result


@pytest.mark.asyncio
async def test_do_schedule_parse_error(mock_scheduler):
    from core.telegram.handlers import _do_schedule
    result = await _do_schedule('add cron "unclosed', mock_scheduler, "telegram", 42)
    assert "Parse error" in result or "No closing quotation" in result


# ---------------------------------------------------------------------------
# notify_telegram flag set when origin == "telegram"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_loop_job_sets_notify_telegram(mock_scheduler):
    from core.telegram.handlers import _do_schedule
    await _do_schedule('add loop 1m "task"', mock_scheduler, "telegram", 99)
    job = mock_scheduler.add_job.call_args[0][0]
    assert job.notify_telegram is True
    assert job.chat_id == 99


@pytest.mark.asyncio
async def test_loop_job_no_notify_for_cli(mock_scheduler):
    from core.telegram.handlers import _do_schedule
    await _do_schedule('add loop 1m "task"', mock_scheduler, "cli", None)
    job = mock_scheduler.add_job.call_args[0][0]
    assert job.notify_telegram is False


# ---------------------------------------------------------------------------
# bot.py — start_bot returns None when disabled or no token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_bot_disabled():
    from core.telegram.bot import start_bot
    result = await start_bot({"telegram": {"enabled": False}}, None, None, None)
    assert result is None


@pytest.mark.asyncio
async def test_start_bot_no_token(capsys):
    from core.telegram.bot import start_bot
    result = await start_bot({"telegram": {"enabled": True, "bot_token": ""}}, None, None, None)
    assert result is None
    captured = capsys.readouterr()
    assert "bot_token" in captured.out


@pytest.mark.asyncio
async def test_start_bot_no_allowed_ids_warns(capsys):
    from core.telegram.bot import start_bot

    mock_app = MagicMock()
    mock_app.initialize = AsyncMock()
    mock_app.start = AsyncMock()
    mock_app.updater = MagicMock()
    mock_app.updater.start_polling = AsyncMock()
    mock_app.bot = MagicMock()
    mock_app.add_handler = MagicMock()

    mock_builder = MagicMock()
    mock_builder.token.return_value = mock_builder
    mock_builder.build.return_value = mock_app

    mock_router = MagicMock()
    mock_router.set_telegram_bot = MagicMock()

    config = {"telegram": {"enabled": True, "bot_token": "fake_token", "allowed_ids": []}}

    with patch("core.telegram.bot.make_handlers", return_value=[]), \
         patch("telegram.ext.Application.builder", return_value=mock_builder):
        result = await start_bot(config, MagicMock(), mock_router, MagicMock())

    captured = capsys.readouterr()
    assert "allowed_ids is empty" in captured.out


# ---------------------------------------------------------------------------
# stop_bot is a no-op when app is None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_bot_none():
    from core.telegram.bot import stop_bot
    await stop_bot(None)   # must not raise


@pytest.mark.asyncio
async def test_stop_bot_calls_shutdown():
    from core.telegram.bot import stop_bot

    mock_app = MagicMock()
    mock_app.updater = MagicMock()
    mock_app.updater.stop = AsyncMock()
    mock_app.stop = AsyncMock()
    mock_app.shutdown = AsyncMock()

    await stop_bot(mock_app)

    mock_app.updater.stop.assert_awaited_once()
    mock_app.stop.assert_awaited_once()
    mock_app.shutdown.assert_awaited_once()
