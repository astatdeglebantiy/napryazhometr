import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards import CALLBACK_CHECK_STATUS, get_status_keyboard
from config import config
import messages
from models.power import PowerSnapshot
from services.ha_client import HomeAssistantClient
from services.power_service import PowerService
from storage.state_store import StateStore

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start", "status_btn"))
async def cmd_start(message: Message):
    """Sends the network status check button prompt."""
    await message.answer(
        messages.CMD_START_PROMPT,
        reply_markup=get_status_keyboard(),
    )


@router.callback_query(F.data == CALLBACK_CHECK_STATUS)
async def handle_check_status_popup(
    callback: CallbackQuery,
    ha_client: HomeAssistantClient,
    power_service: PowerService,
    store: StateStore,
):
    """Queries Home Assistant telemetry and responds with an alert popup."""
    power_state = await ha_client.get_entity_state(config.power_binary_sensor)
    voltage_state = await ha_client.get_entity_state(config.voltage_sensor)
    freq_state = await ha_client.get_entity_state(config.frequency_sensor)
    dtek_state = await ha_client.get_entity_state(config.dtek_electricity_status)

    is_on = (power_state.get("state") == "on") if power_state else False
    voltage = _parse_float(voltage_state)
    frequency = _parse_float(freq_state)
    dtek_status = dtek_state.get("state", "normal") if dtek_state else "normal"

    snapshot = PowerSnapshot(
        is_on=is_on,
        voltage=voltage,
        frequency=frequency,
        dtek_status=dtek_status,
        last_power_on_ts=store.last_power_on_ts,
        last_power_off_ts=store.last_power_off_ts,
    )

    alert_message = power_service.build_popup_message(snapshot)
    await callback.answer(text=alert_message, show_alert=True)


def _parse_float(state: dict | None, default: float = 0.0) -> float:
    """Safely extracts a float value from an entity state payload."""
    if not state:
        return default
    try:
        return float(state.get("state", default))
    except (ValueError, TypeError):
        return default
