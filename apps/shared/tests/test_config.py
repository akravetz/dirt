from __future__ import annotations

import pytest
from pydantic import ValidationError

from dirt_shared.config import Settings, ThermoForgeConfig

THERMOFORGE_ENV_VARS = (
    "THERMOFORGE_NIGHT_LEVEL",
    "THERMOFORGE_POLL_INTERVAL",
    "THERMOFORGE_CONNECT_TIMEOUT_S",
    "THERMOFORGE_OFFLINE_ALERT_FAILURES",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_ALLOWED_USER_ID",
)


def test_thermoforge_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in THERMOFORGE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.thermoforge() == ThermoForgeConfig(
        night_level=4,
        poll_interval=30,
        connect_timeout_s=15,
        offline_alert_failures=2,
        state_path=settings.data_dir / "logs" / "heater" / "state.json",
        telegram_bot_token="",
        telegram_chat_id="",
    )


def test_thermoforge_config_reads_env_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("THERMOFORGE_NIGHT_LEVEL", "7")
    monkeypatch.setenv("THERMOFORGE_POLL_INTERVAL", "45")
    monkeypatch.setenv("THERMOFORGE_CONNECT_TIMEOUT_S", "20")
    monkeypatch.setenv("THERMOFORGE_OFFLINE_ALERT_FAILURES", "3")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-1")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat-1")

    settings = Settings(_env_file=None)

    assert settings.thermoforge() == ThermoForgeConfig(
        night_level=7,
        poll_interval=45,
        connect_timeout_s=20,
        offline_alert_failures=3,
        state_path=settings.data_dir / "logs" / "heater" / "state.json",
        telegram_bot_token="token-1",
        telegram_chat_id="chat-1",
    )


def test_telegram_allowed_user_id_alias_still_populates_thermoforge_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in THERMOFORGE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-1")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_ID", "legacy-chat")

    settings = Settings(_env_file=None)

    assert settings.thermoforge().telegram_bot_token == "token-1"
    assert settings.thermoforge().telegram_chat_id == "legacy-chat"


@pytest.mark.parametrize("level", ["-1", "11"])
def test_thermoforge_night_level_must_be_supported(
    monkeypatch: pytest.MonkeyPatch, level: str
) -> None:
    monkeypatch.setenv("THERMOFORGE_NIGHT_LEVEL", level)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
