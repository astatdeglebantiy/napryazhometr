import os
from config import Config


def test_config_defaults(monkeypatch):
    monkeypatch.delenv("HA_BASE_URL", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    cfg = Config()
    assert cfg.ha_base_url == "http://homeassistant.local:8123"
    assert cfg.timezone == "Europe/Kyiv"
    assert cfg.calendar_planned == "calendar.kyiv_region_4_1_planned_outages"


def test_config_dev_mode(monkeypatch):
    """Проверяет, что при is_dev подставляются dev-токены и изолированные файлы."""
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("DEV_TELEGRAM_BOT_TOKEN", "999:dev_bot")
    monkeypatch.setenv("DEV_TELEGRAM_CHAT_ID", "-100777")

    cfg = Config(
        is_dev=True,
        bot_token=os.getenv("DEV_TELEGRAM_BOT_TOKEN"),
        target_chat_id=os.getenv("DEV_TELEGRAM_CHAT_ID"),
        state_file_path="./bot_state.dev.json",
        msg_prefix="🧪 <b>[DEV]</b> ",
    )

    assert cfg.is_dev is True
    assert cfg.bot_token == "999:dev_bot"
    assert cfg.target_chat_id == "-100777"
    assert "dev" in cfg.state_file_path
    assert "[DEV]" in cfg.msg_prefix


def test_config_env_overrides(monkeypatch):
    monkeypatch.setenv("HA_BASE_URL", "http://custom-server:9000")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-999")
    cfg = Config(
        ha_base_url=os.getenv("HA_BASE_URL"),
        target_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    )
    assert cfg.ha_base_url == "http://custom-server:9000"
    assert cfg.target_chat_id == "-999"
