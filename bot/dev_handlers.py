import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import messages
from services.frequency_monitor import FrequencyMonitor
from services.power_monitor import PowerMonitor
from services.schedule_publisher import SchedulePublisher
from services.voltage_monitor import VoltageMonitor

logger = logging.getLogger(__name__)
dev_router = Router()


def get_dev_keyboard() -> InlineKeyboardMarkup:
    """Builds inline keyboard for triggering dev actions."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Надіслати графік", callback_data="dev:schedule"),
            ],
            [
                InlineKeyboardButton(text="🟢 Світло увімкнено", callback_data="dev:power_on"),
                InlineKeyboardButton(text="🔴 Світло вимкнено", callback_data="dev:power_off"),
            ],
            [
                InlineKeyboardButton(text="⚠️ Низька напруга (185V)", callback_data="dev:volt_low"),
                InlineKeyboardButton(text="🚨 Критична напруга (168V)", callback_data="dev:volt_crit"),
            ],
            [
                InlineKeyboardButton(text="⚠️ Висока напруга (258V)", callback_data="dev:volt_high"),
                InlineKeyboardButton(text="🚨 Критична частота (49.1Hz)", callback_data="dev:freq_crit"),
            ],
        ]
    )


# --- Commands ---

@dev_router.message(Command("dev", "test"))
async def cmd_dev_menu(message: Message):
    """Displays the interactive dev test menu."""
    await message.answer(messages.DEV_MENU_PROMPT, reply_markup=get_dev_keyboard())


@dev_router.message(Command("test_schedule"))
async def cmd_test_schedule(message: Message, schedule_publisher: SchedulePublisher):
    """Force publishes the schedule animation."""
    await message.answer("⏳ Generating and dispatching schedule...")
    schedule_publisher.trigger_update(force=True)


@dev_router.message(Command("test_power_on"))
async def cmd_test_power_on(message: Message, power_monitor: PowerMonitor):
    """Simulates a power-on state transition."""
    await message.answer("⚡️ Simulating power-on event...")
    await power_monitor.handle_power_state_change(new_state="on", old_state="off")


@dev_router.message(Command("test_power_off"))
async def cmd_test_power_off(message: Message, power_monitor: PowerMonitor):
    """Simulates a power-off state transition."""
    await message.answer("🔌 Simulating power-off event...")
    await power_monitor.handle_power_state_change(new_state="off", old_state="on")


# --- Callbacks ---

@dev_router.callback_query(F.data == "dev:schedule")
async def cb_test_schedule(callback: CallbackQuery, schedule_publisher: SchedulePublisher):
    await callback.answer("Schedule generation triggered")
    schedule_publisher.trigger_update(force=True)


@dev_router.callback_query(F.data == "dev:power_on")
async def cb_test_power_on(callback: CallbackQuery, power_monitor: PowerMonitor):
    await callback.answer("Simulating power ON")
    await power_monitor.handle_power_state_change(new_state="on", old_state="off")


@dev_router.callback_query(F.data == "dev:power_off")
async def cb_test_power_off(callback: CallbackQuery, power_monitor: PowerMonitor):
    await callback.answer("Simulating power OFF")
    await power_monitor.handle_power_state_change(new_state="off", old_state="on")


@dev_router.callback_query(F.data == "dev:volt_low")
async def cb_test_volt_low(callback: CallbackQuery, voltage_monitor: VoltageMonitor):
    await callback.answer("Simulating low voltage")
    await voltage_monitor.handle_voltage_change(v=185.0, is_power_on=True)


@dev_router.callback_query(F.data == "dev:volt_crit")
async def cb_test_volt_crit(callback: CallbackQuery, voltage_monitor: VoltageMonitor):
    await callback.answer("Simulating critical low voltage")
    await voltage_monitor.handle_voltage_change(v=168.0, is_power_on=True)


@dev_router.callback_query(F.data == "dev:volt_high")
async def cb_test_volt_high(callback: CallbackQuery, voltage_monitor: VoltageMonitor):
    await callback.answer("Simulating high voltage")
    await voltage_monitor.handle_voltage_change(v=258.0, is_power_on=True)


@dev_router.callback_query(F.data == "dev:freq_crit")
async def cb_test_freq_crit(callback: CallbackQuery, frequency_monitor: FrequencyMonitor):
    await callback.answer("Simulating critical low frequency")
    await frequency_monitor.handle_frequency_change(hz=49.10, is_power_on=True)
