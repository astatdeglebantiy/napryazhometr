from dataclasses import dataclass
import os
import sys
from dotenv import load_dotenv

load_dotenv()


def check_is_dev() -> bool:
    """Checks whether the application runs in development mode via env or CLI flags."""
    env_mode = os.getenv("APP_ENV", "prod").lower() == "dev"
    cli_flag = "--dev" in sys.argv
    return env_mode or cli_flag


@dataclass(frozen=True)
class Config:
    """Application configuration container."""

    # Runtime Environment
    is_dev: bool = check_is_dev()

    # Home Assistant Connection
    ha_base_url: str = os.getenv("HA_BASE_URL", "http://homeassistant.local:8123")
    ha_ws_url: str = os.getenv("HA_WS_URL", "ws://homeassistant.local:8123/api/websocket")
    ha_token: str = os.getenv("HA_TOKEN", "")

    # Home Assistant Entity IDs (configurable via .env with fallback defaults)
    power_binary_sensor: str = os.getenv(
        "HA_POWER_BINARY_SENSOR", "binary_sensor.nalichie_elektrichestva"
    )
    voltage_sensor: str = os.getenv(
        "HA_VOLTAGE_SENSOR", "sensor.survival_node_pzem_voltage"
    )
    frequency_sensor: str = os.getenv(
        "HA_FREQUENCY_SENSOR", "sensor.survival_node_pzem_frequency_chastota_seti"
    )
    dtek_electricity_status: str = os.getenv(
        "HA_DTEK_ELECTRICITY_STATUS", "sensor.kyiv_region_4_1_electricity"
    )
    dtek_schedule_updated_on: str = os.getenv(
        "HA_DTEK_SCHEDULE_UPDATED_ON", "sensor.kyiv_region_4_1_schedule_updated_on"
    )
    dtek_next_planned_outage: str = os.getenv(
        "HA_DTEK_NEXT_PLANNED_OUTAGE", "sensor.kyiv_region_4_1_next_planned_outage"
    )
    dtek_next_scheduled_outage: str = os.getenv(
        "HA_DTEK_NEXT_SCHEDULED_OUTAGE", "sensor.kyiv_region_4_1_next_scheduled_outage"
    )
    dtek_next_connectivity: str = os.getenv(
        "HA_DTEK_NEXT_CONNECTIVITY", "sensor.kyiv_region_4_1_next_connectivity"
    )
    calendar_planned: str = os.getenv(
        "HA_CALENDAR_PLANNED", "calendar.kyiv_region_4_1_planned_outages"
    )
    calendar_scheduled: str = os.getenv(
        "HA_CALENDAR_SCHEDULED", "calendar.kyiv_region_4_1_scheduled_outages"
    )

    # Static Assets Paths
    logo_path: str = os.getenv("LOGO_PATH", "./assets/logo.png")
    font_path: str = os.getenv("FONT_PATH", "./assets/font.ttf")

    # Localization and Metadata
    timezone: str = os.getenv("TIMEZONE", "Europe/Kyiv")
    group_name: str = os.getenv("GROUP_NAME", "Група 4.1")

    # Dynamic Telegram Credentials & Artifact Paths
    @property
    def bot_token(self) -> str:
        """Returns the appropriate bot token based on environment mode."""
        if self.is_dev:
            return os.getenv("DEV_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
        return os.getenv("TELEGRAM_BOT_TOKEN", "")

    @property
    def target_chat_id(self) -> str:
        """Returns target chat ID based on environment mode."""
        if self.is_dev:
            return os.getenv("DEV_TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID", "")
        return os.getenv("TELEGRAM_CHAT_ID", "")

    @property
    def msg_dev_prefix(self) -> str:
        """Prefix prepended to messages in development mode."""
        return "🧪 <b>[DEV]</b> " if self.is_dev else ""

    # @property
    # def msg_suffix(self) -> str:
    #     """Suffix appended to messages for ."""
    #     return "\n\n<tg-emoji emoji-id='5312104457515837830'>🔵</tg-emoji> <a href='https://t.me/NapryazhometrPK41'>Напряжометр</a>"

    @property
    def state_file_path(self) -> str:
        """State persistence file stored in data directory to support clean Docker volume mounts."""
        default_path = "./data/bot_state.dev.json" if self.is_dev else "./data/bot_state.json"
        return os.getenv("STATE_FILE_PATH", default_path)

    @property
    def output_image_path(self) -> str:
        """Video render output path isolated between dev and prod environments."""
        default_path = "./svitlo_graph.dev.mp4" if self.is_dev else "./svitlo_graph.mp4"
        return os.getenv("OUTPUT_IMAGE_PATH", default_path)


config = Config()
