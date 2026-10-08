import os
import pytest
from datetime import datetime
import pytz
from config import Config
from storage.state_store import StateStore
from services.power_service import PowerService
from services.schedule_service import ScheduleService

@pytest.fixture
def mock_env(monkeypatch):
    """Изолирует окружение тестов."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:TEST_TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100111222333")
    monkeypatch.setenv("HA_BASE_URL", "http://test-ha:8123")
    monkeypatch.setenv("HA_WS_URL", "ws://test-ha:8123/api/websocket")
    monkeypatch.setenv("HA_TOKEN", "test_ha_token")

@pytest.fixture
def test_config(mock_env, tmp_path):
    return Config(
        state_file_path=str(tmp_path / "test_state.json"),
        output_image_path=str(tmp_path / "test_graph.png"),
        timezone="Europe/Kyiv"
    )

@pytest.fixture
def kyiv_tz():
    return pytz.timezone("Europe/Kyiv")

@pytest.fixture
def state_store(tmp_path):
    file_path = tmp_path / "state_test.json"
    return StateStore(str(file_path))

@pytest.fixture
def power_service(test_config, state_store):
    return PowerService(test_config, state_store)

@pytest.fixture
def schedule_service():
    return ScheduleService(tz_name="Europe/Kyiv")
