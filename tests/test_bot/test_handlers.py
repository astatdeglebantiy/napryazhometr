import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import CallbackQuery, Message, User, Chat
from bot.handlers import cmd_start, handle_check_status_popup

@pytest.mark.asyncio
async def test_cmd_start():
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    await cmd_start(message)
    message.answer.assert_called_once()
    assert "Натисніть кнопку" in message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_handle_check_status_popup(mocker, state_store, power_service):
    # Мокаем HA Client
    mock_ha = mocker.MagicMock()
    mock_ha.get_entity_state = AsyncMock(side_effect=[
        {"state": "on"},       # power_state
        {"state": "225.4"},    # voltage
        {"state": "normal"}    # dtek_state
    ])

    callback = MagicMock(spec=CallbackQuery)
    callback.answer = AsyncMock()

    await handle_check_status_popup(
        callback=callback,
        ha_client=mock_ha,
        power_service=power_service,
        store=state_store
    )

    callback.answer.assert_called_once()
    call_kwargs = callback.answer.call_args[1]
    assert call_kwargs.get("show_alert") is True
    assert "💡 Є" in call_kwargs.get("text")
    assert "225.4V" in call_kwargs.get("text")
