import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from bot.keyboards import get_status_keyboard
from config import config
from models.power import PowerSnapshot
from services.ha_client import HomeAssistantClient
from services.power_service import PowerService
from storage.state_store import StateStore

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start", "status_btn"))
async def cmd_start(message: Message):
    """Отправляет кнопку для проверки статуса."""
    await message.answer(
        "Натисніть кнопку нижче, щоб отримати швидкий статус живлення:",
        reply_markup=get_status_keyboard(),
    )


@router.callback_query(F.data == "/check_status")
async def handle_check_status_popup(
    callback: CallbackQuery,
    ha_client: HomeAssistantClient,
    power_service: PowerService,
    store: StateStore,
):
    """Обрабатывает нажатие кнопки и выводит Show Alert Popup."""
    # Получаем актуальные данные из Home Assistant
    # Получаем актуальные данные
    power_state = await ha_client.get_entity_state(config.power_binary_sensor)
    voltage_state = await ha_client.get_entity_state(config.voltage_sensor)
    freq_state = await ha_client.get_entity_state(config.frequency_sensor)
    dtek_state = await ha_client.get_entity_state(config.dtek_electricity_status)

    is_on = (power_state.get("state") == "on") if power_state else False

    try:
        voltage = float(voltage_state.get("state", 0.0)) if voltage_state else 0.0
    except (ValueError, TypeError):
        voltage = 0.0

    try:
        frequency = float(freq_state.get("state", 0.0)) if freq_state else 0.0
    except (ValueError, TypeError):
        frequency = 0.0

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

    # Выводим как модальный попап (show_alert=True)
    await callback.answer(text=alert_message, show_alert=True)
