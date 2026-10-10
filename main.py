import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.handlers import router
from config import config
from services.event_card_service import EventCardService
from services.frequency_monitor import FrequencyMonitor
from services.graph_service import GraphService
from services.ha_client import HomeAssistantClient
from services.ha_dispatcher import HomeAssistantDispatcher
from services.power_monitor import PowerMonitor
from services.power_service import PowerService
from services.schedule_publisher import SchedulePublisher
from services.schedule_service import ScheduleService
from services.voltage_monitor import VoltageMonitor
from storage.state_store import StateStore

# Logging setup
log_level = logging.DEBUG if config.is_dev else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("napryazhometr")


async def main():
    if not config.bot_token or not config.target_chat_id:
        logger.error("Missing bot token or target chat id (is_dev=%s)", config.is_dev)
        sys.exit(1)

    # 1. Telegram Bot Core
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # 2. State & External Clients
    store = StateStore(config.state_file_path)
    ha_client = HomeAssistantClient(
        base_url=config.ha_base_url,
        ws_url=config.ha_ws_url,
        token=config.ha_token,
        tz_name=config.timezone,
    )

    # 3. Domain Services
    power_service = PowerService(config, store)
    schedule_service = ScheduleService(config.timezone)
    graph_service = GraphService(
        tz_name=config.timezone,
        font_path=config.font_path,
        logo_path=config.logo_path,
    )
    event_card_service = EventCardService(
        tz_name=config.timezone,
        font_path=config.font_path,
        logo_path=config.logo_path,
    )

    # 4. State Monitors & Dispatcher
    voltage_monitor = VoltageMonitor(bot, config, store)
    frequency_monitor = FrequencyMonitor(bot, config, store)
    schedule_publisher = SchedulePublisher(bot, config, store, ha_client, schedule_service, graph_service)
    power_monitor = PowerMonitor(bot, config, store, ha_client, power_service, event_card_service)

    dispatcher = HomeAssistantDispatcher(
        config=config,
        ha_client=ha_client,
        schedule_pub=schedule_publisher,
        power_mon=power_monitor,
        voltage_mon=voltage_monitor,
        freq_mon=frequency_monitor,
    )

    # 5. Dependency Injection for Handlers
    dp["ha_client"] = ha_client
    dp["power_service"] = power_service
    dp["store"] = store
    dp["schedule_publisher"] = schedule_publisher
    dp["power_monitor"] = power_monitor
    dp["voltage_monitor"] = voltage_monitor
    dp["frequency_monitor"] = frequency_monitor

    # 6. Routers Registration
    dp.include_router(router)

    if config.is_dev:
        from bot.dev_handlers import dev_router
        dp.include_router(dev_router)
        logger.info("Development router successfully attached (/dev command available).")

    # 7. Background Event Listener
    ws_task = asyncio.create_task(ha_client.listen_events(dispatcher.dispatch_event))

    # Catch up on any missed events (schedules, power transitions, alerts) while offline
    asyncio.create_task(dispatcher.sync_on_startup())

    logger.info("Bot successfully started. Listening to Home Assistant events...")
    try:
        await dp.start_polling(bot)
    finally:
        ws_task.cancel()
        await ha_client.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
