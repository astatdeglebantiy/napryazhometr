import os
import sys
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def check_is_dev() -> bool:
    """Определяет, запущен ли проект в dev-режиме (через env или флаг --dev)."""
    env_mode = os.getenv("APP_ENV", "prod").lower() == "dev"
    cli_flag = "--dev" in sys.argv
    return env_mode or cli_flag


@dataclass(frozen=True)
class Config:
    # Окружение
    is_dev: bool = check_is_dev()

    # Токены и чаты (автоматически выбираются нужные в зависимости от is_dev)
    bot_token: str = (
        os.getenv("DEV_TELEGRAM_BOT_TOKEN", "")
        if is_dev
        else os.getenv("TELEGRAM_BOT_TOKEN", "")
    )
    target_chat_id: str = (
        os.getenv("DEV_TELEGRAM_CHAT_ID", "")
        if is_dev
        else os.getenv("TELEGRAM_CHAT_ID", "")
    )

    # Префикс сообщений для отличия в Telegram
    msg_prefix: str = "🧪 <b>[DEV]</b> " if is_dev else ""

    # Home Assistant
    ha_base_url: str = os.getenv("HA_BASE_URL", "http://homeassistant.local:8123")
    ha_ws_url: str = os.getenv(
        "HA_WS_URL", "ws://homeassistant.local:8123/api/websocket"
    )
    ha_token: str = os.getenv("HA_TOKEN", "")

    # HA Entity IDs
    power_binary_sensor: str = "binary_sensor.nalichie_elektrichestva"
    voltage_sensor: str = "sensor.survival_node_pzem_voltage"
    frequency_sensor: str = "sensor.survival_node_pzem_frequency_chastota_seti"
    dtek_electricity_status: str = "sensor.kyiv_region_4_1_electricity"
    dtek_schedule_updated_on: str = "sensor.kyiv_region_4_1_schedule_updated_on"
    dtek_next_planned_outage: str = "sensor.kyiv_region_4_1_next_planned_outage"
    dtek_next_scheduled_outage: str = "sensor.kyiv_region_4_1_next_scheduled_outage"
    dtek_next_connectivity: str = "sensor.kyiv_region_4_1_next_connectivity"
    calendar_planned: str = "calendar.kyiv_region_4_1_planned_outages"
    calendar_scheduled: str = "calendar.kyiv_region_4_1_scheduled_outages"

    # Изоляция файлов между prod и dev
    state_file_path: str = (
        "./bot_state.dev.json" if is_dev else "./bot_state.json"
    )
    output_image_path: str = (
        "./svitlo_graph.dev.mp4" if is_dev else "./svitlo_graph.mp4"
    )

    logo_path: str = "./assets/logo.png"
    font_path: str = "./assets/font.ttf"

    # Прочие настройки
    timezone: str = "Europe/Kyiv"
    group_name: str = "Група 4.1"


config = Config()
