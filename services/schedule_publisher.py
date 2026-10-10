import asyncio
from datetime import datetime, timedelta
import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
import pytz

from config import Config
import messages
from services.graph_service import GraphService
from services.ha_client import HomeAssistantClient
from services.schedule_service import ScheduleService
from storage.state_store import StateStore

logger = logging.getLogger(__name__)


class SchedulePublisher:
    """Manages schedule change detection, graph generation, and publication."""

    def __init__(
        self,
        bot: Bot,
        config: Config,
        store: StateStore,
        ha_client: HomeAssistantClient,
        schedule_srv: ScheduleService,
        graph_srv: GraphService,
    ):
        self.bot = bot
        self.cfg = config
        self.store = store
        self.ha = ha_client
        self.schedule_srv = schedule_srv
        self.graph_srv = graph_srv
        self.tz = pytz.timezone(config.timezone)
        self._task: asyncio.Task | None = None

    def trigger_update(self, force: bool = False):
        """Spawns an update task if one is not already running."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_cycle(force=force))

    async def check_and_publish(self, force: bool = False) -> bool:
        """Checks if calendar schedule changed and publishes it immediately.

        Returns True if a new schedule was published, False otherwise.
        """
        now = datetime.now(self.tz)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        planned = await self.ha.get_calendar_events(self.cfg.calendar_planned, today, 48)
        scheduled = await self.ha.get_calendar_events(self.cfg.calendar_scheduled, today, 48)

        signature = self.schedule_srv.compute_signature(planned, scheduled, today.date())

        if force or signature != self.store.last_schedule_hash:
            logger.info("Schedule publishing triggered (force=%s)...", force)
            self.store.last_schedule_hash = signature
            self.store.save()

            # Read telemetry
            v_state = await self.ha.get_entity_state(self.cfg.voltage_sensor)
            f_state = await self.ha.get_entity_state(self.cfg.frequency_sensor)
            current_v = self._format_voltage(v_state)
            current_hz = self._format_freq(f_state)

            # Generate video
            logger.info("Generating MP4 schedule chart...")
            self.graph_srv.generate_chart(
                planned=planned,
                scheduled=scheduled,
                out_path=self.cfg.output_image_path,
                voltage_val=current_v.replace(" V", ""),
                frequency_val=current_hz.replace(" Hz", ""),
                group_name=self.cfg.group_name,
            )
            logger.info("Chart generation completed.")

            today_text = self.schedule_srv.build_day_timeline(planned, today.date(), False)
            tomorrow_text = self.schedule_srv.build_day_timeline(
                planned, (today + timedelta(days=1)).date(), True
            )

            upd_sensor = await self.ha.get_entity_state(self.cfg.dtek_schedule_updated_on)
            upd_str = self._format_updated_time(upd_sensor)
            net_status = f"{current_v}" + (f" • {current_hz}" if current_hz else "")

            caption = messages.SCHEDULE_UPDATE_CAPTION.format(
                group_name=self.cfg.group_name,
                upd_str=upd_str,
                net_status=net_status,
                today_date=now.strftime("%d.%m"),
                today_text=today_text,
                tomorrow_date=(today + timedelta(days=1)).strftime("%d.%m"),
                tomorrow_text=tomorrow_text,
            )

            await self.bot.send_animation(
                chat_id=self.cfg.target_chat_id,
                animation=FSInputFile(self.cfg.output_image_path),
                caption=self.cfg.msg_dev_prefix + caption.strip(),
                parse_mode=ParseMode.HTML,
            )
            logger.info("Schedule successfully published to Telegram.")
            return True

        return False

    async def _run_cycle(self, force: bool = False):
        """Retries checking for updates up to 6 times with a delay (used for HA events)."""
        try:
            for attempt in range(1, 7):
                logger.info("Checking schedule updates (attempt %d of 6)...", attempt)
                published = await self.check_and_publish(force=force)
                if published:
                    break
                await asyncio.sleep(10)
        except Exception as e:
            logger.exception("Failed to publish schedule update: %s", e)

    @staticmethod
    def _format_voltage(state: dict | None) -> str:
        """Formats raw voltage sensor payload to rounded integer string."""
        try:
            return f"{int(round(float(state['state'])))} V" if state else "—"
        except (ValueError, TypeError, KeyError):
            return "—"

    @staticmethod
    def _format_freq(state: dict | None) -> str:
        """Formats raw frequency sensor payload to one-decimal string."""
        try:
            return f"{float(state['state']):.1f} Hz" if state else ""
        except (ValueError, TypeError, KeyError):
            return ""

    def _format_updated_time(self, sensor: dict | None) -> str:
        """Parses DTEK timestamp and returns formatted Kyiv time."""
        if not sensor:
            return "—"
        try:
            dt = datetime.fromisoformat(sensor["state"].replace("Z", "+00:00")).astimezone(self.tz)
            return dt.strftime("%H:%M")
        except Exception:
            return str(sensor.get("state", "—"))[:5]
