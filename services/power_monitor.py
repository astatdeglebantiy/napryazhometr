from datetime import datetime
import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
import pytz

from config import Config
import messages
from models.power import FrequencyAlert, VoltageAlert
from models.schedule import CalendarEvent
from services.event_card_service import EventCardService
from services.ha_client import HomeAssistantClient
from services.power_service import PowerService
from storage.state_store import StateStore

logger = logging.getLogger(__name__)


class PowerMonitor:
    def __init__(
        self,
        bot: Bot,
        config: Config,
        store: StateStore,
        ha_client: HomeAssistantClient,
        power_srv: PowerService,
        event_card_srv: EventCardService,
    ):
        self.bot = bot
        self.cfg = config
        self.store = store
        self.ha = ha_client
        self.power_srv = power_srv
        self.event_card_srv = event_card_srv
        self.tz = pytz.timezone(config.timezone)

    async def handle_power_state_change(self, new_state: str, old_state: str):
        """Dispatches power change events based on new and previous binary states."""
        if new_state == "on" and old_state != "on":
            await self._process_transition(is_on=True)
        elif new_state == "off" and old_state != "off":
            await self._process_transition(is_on=False)

    async def _process_transition(self, is_on: bool):
        """Unified processing pipeline for both power-on and power-off events."""
        now_dt = datetime.now(self.tz)
        now_ts = now_dt.timestamp()

        # Reset active alerts
        self.store.active_voltage_alert = VoltageAlert.NONE
        if not is_on:
            self.store.active_frequency_alert = FrequencyAlert.NONE

        # Record state timestamps and compute duration of the previous period
        if is_on:
            elapsed = int(now_ts - self.store.last_power_off_ts) if self.store.last_power_off_ts else None
            dur_template = messages.DURATION_OFF_SUMMARY
            self.store.last_power_on_ts = now_ts
        else:
            elapsed = int(now_ts - self.store.last_power_on_ts) if self.store.last_power_on_ts else None
            dur_template = messages.DURATION_ON_SUMMARY
            self.store.last_power_off_ts = now_ts

        self.store.save()

        # Fetch telemetry and schedule status from Home Assistant
        v_state = await self.ha.get_entity_state(self.cfg.voltage_sensor)
        f_state = await self.ha.get_entity_state(self.cfg.frequency_sensor)
        dtek_state = await self.ha.get_entity_state(self.cfg.dtek_electricity_status)
        planned_events = await self.ha.get_calendar_events(self.cfg.calendar_planned, now_dt, 24)

        voltage = self._parse_float(v_state) if is_on else 0.0
        freq = self._parse_float(f_state, default=50.0) if is_on else None
        dtek_status = dtek_state.get("state", "normal") if dtek_state else "normal"

        plan_badge = self._get_plan_badge(dtek_status, is_on)
        dur_str = dur_template.format(duration=self.power_srv.format_duration(elapsed)) if elapsed else ""

        # Fetch factual binary sensor history for the current day
        today_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        fact_history = await self.ha.get_entity_history(self.cfg.power_binary_sensor, today_start, now_dt)

        # Generate event comparison video (Meme -> Status Card -> Plan vs Fact)
        anim_path = "./event_power_on.mp4" if is_on else "./event_power_off.mp4"
        self.event_card_srv.generate_event_video(
            is_power_on=is_on,
            voltage_val=f"{int(round(voltage))}" if is_on else "0",
            freq_val=f"{freq:.1f}" if freq is not None else "—",
            duration_str=dur_str,
            plan_badge_text=plan_badge,
            planned_events=planned_events,
            fact_history=fact_history,
            out_path=anim_path,
            group_name=self.cfg.group_name,
        )

        # Compose message text
        if is_on:
            next_outage_str = self._calculate_next_outage(planned_events, now_dt)
            msg = self.cfg.msg_prefix + self.power_srv.build_power_on_message(voltage, dtek_status, next_outage_str)
        else:
            msg = self.cfg.msg_prefix + self.power_srv.build_power_off_message(dtek_status, None)

        # Dispatch animated notification
        await self.bot.send_animation(
            self.cfg.target_chat_id,
            animation=FSInputFile(anim_path),
            caption=msg,
            parse_mode=ParseMode.HTML,
        )

    @staticmethod
    def _get_plan_badge(dtek_status: str, is_on: bool) -> str:
        """Looks up the appropriate plan adherence badge using a pre-configured mapping."""
        fallback = messages.DEFAULT_BADGE_ON if is_on else messages.DEFAULT_BADGE_OFF
        return messages.PLAN_BADGES.get((is_on, dtek_status), fallback)

    @staticmethod
    def _calculate_next_outage(planned_events: list[CalendarEvent], now_dt: datetime) -> str | None:
        """Finds the earliest upcoming planned outage from calendar events."""
        future = [e for e in planned_events if e.start > now_dt]
        if not future:
            return None
        next_e = min(future, key=lambda e: e.start)
        if next_e.start.date() == now_dt.date():
            return next_e.start.strftime("%H:%M")
        return next_e.start.strftime("%H:%M (%d.%m)")

    @staticmethod
    def _parse_float(state: dict | None, default: float = 0.0) -> float:
        """Safely extracts a float value from an entity state payload."""
        try:
            return float(state["state"]) if state else default
        except (ValueError, TypeError, KeyError):
            return default
