import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from services.ha_client import HomeAssistantClient


@pytest.mark.asyncio
async def test_ha_client_get_entity_state(mocker):
    ha_client = HomeAssistantClient(
        "http://fake-ha:8123", "ws://fake-ha:8123/ws", "secret_token"
    )

    # Мокаем aiohttp response
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={"entity_id": "sensor.voltage", "state": "229.4"}
    )

    mock_get_ctx = MagicMock()
    mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_get_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get.return_value = mock_get_ctx
    mock_session.closed = False

    mocker.patch.object(ha_client, "get_session", AsyncMock(return_value=mock_session))

    state = await ha_client.get_entity_state("sensor.voltage")
    assert state is not None
    assert state["state"] == "229.4"
    mock_session.get.assert_called_once_with(
        "http://fake-ha:8123/api/states/sensor.voltage"
    )


@pytest.mark.asyncio
async def test_ha_client_calendar_events_parsing(mocker, kyiv_tz):
    ha_client = HomeAssistantClient(
        "http://fake-ha:8123", "ws://fake-ha:8123/ws", "secret_token"
    )

    calendar_data = [
        {
            "start": {"dateTime": "2026-03-04T12:00:00+02:00"},
            "end": {"dateTime": "2026-03-04T16:00:00+02:00"},
            "summary": "Відключення",
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=calendar_data)

    mock_get_ctx = MagicMock()
    mock_get_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_get_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get.return_value = mock_get_ctx
    mock_session.closed = False

    mocker.patch.object(ha_client, "get_session", AsyncMock(return_value=mock_session))

    events = await ha_client.get_calendar_events(
        "calendar.test",
        start=kyiv_tz.localize(datetime(2026, 3, 4, 0, 0)),
    )

    assert len(events) == 1
    assert events[0].summary == "Відключення"
    assert events[0].start.hour == 12
    assert events[0].end.hour == 16
