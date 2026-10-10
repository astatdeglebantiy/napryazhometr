from datetime import datetime
import pytz

from config import Config
import messages
from models.power import PowerSnapshot
from storage.state_store import StateStore


class PowerService:
    """Service for formatting power event texts, durations, and status popups."""

    def __init__(self, config: Config, store: StateStore):
        self.cfg = config
        self.store = store
        self.tz = pytz.timezone(config.timezone)

    @staticmethod
    def format_duration(seconds: int) -> str:
        """Formats duration in seconds into human-readable Ukrainian days/hours or hours/minutes without leading zeros."""
        s = max(0, seconds)
        days = s // 86400
        hours = (s % 86400) // 3600
        minutes = (s % 3600) // 60

        # If it lasted 24 hours or longer, show days and hours
        if days > 0:
            return f"{days} доб {hours} год"

        # Otherwise show hours and minutes without leading zeros
        return f"{hours} год {minutes} хв"

    def build_popup_message(self, snapshot: PowerSnapshot) -> str:
        """Constructs text payload for Telegram callback query alert popup."""
        now_ts = datetime.now().timestamp()
        target_ts = snapshot.last_power_on_ts if snapshot.is_on else snapshot.last_power_off_ts

        dur_str = "0 год 0 хв"
        if target_ts:
            dur_str = self.format_duration(int(now_ts - target_ts))

        is_planned = (snapshot.is_on and snapshot.dtek_status == "normal") or (
            not snapshot.is_on and snapshot.dtek_status != "normal"
        )
        plan_badge = messages.POPUP_PLAN_OK if is_planned else messages.POPUP_PLAN_UNEXPECTED
        state_icon = messages.POPUP_LIGHT_ON if snapshot.is_on else messages.POPUP_LIGHT_OFF

        volt_warn = " ⚠️" if 50 < snapshot.voltage < 190 else ""
        freq_str = f" • {snapshot.frequency:.1f}Hz" if snapshot.frequency and snapshot.is_on else ""

        return messages.POPUP_MESSAGE.format(
            state_icon=state_icon,
            dur_str=dur_str,
            plan_badge=plan_badge,
            voltage=snapshot.voltage,
            volt_warn=volt_warn,
            freq_str=freq_str,
        )

    def build_power_on_message(
        self, voltage: float, dtek_status: str, next_outage_str: str | None
    ) -> str:
        """Constructs HTML message when power is restored."""
        now = datetime.now(self.tz)
        dur_str = ""
        if self.store.last_power_off_ts:
            elapsed = int(now.timestamp() - self.store.last_power_off_ts)
            dur_str = messages.POWER_ON_DURATION.format(duration=self.format_duration(elapsed))

        plan_msg = messages.POWER_ON_PLAN_MESSAGES.get(dtek_status, messages.POWER_ON_PLAN_DEFAULT)
        next_str = (
            messages.POWER_ON_NEXT_OUTAGE.format(time_str=next_outage_str)
            if next_outage_str
            else ""
        )

        return messages.POWER_ON_MESSAGE.format(
            voltage=voltage,
            time_str=now.strftime("%H:%M"),
            dur_str=dur_str,
            plan_msg=plan_msg,
            next_str=next_str,
        )

    def build_power_off_message(
        self, dtek_status: str, next_connectivity_str: str | None
    ) -> str:
        """Constructs HTML message when power is cut."""
        now = datetime.now(self.tz)
        dur_str = ""
        if self.store.last_power_on_ts:
            elapsed = int(now.timestamp() - self.store.last_power_on_ts)
            dur_str = messages.POWER_OFF_DURATION.format(duration=self.format_duration(elapsed))

        plan_msg = messages.POWER_OFF_PLAN_MESSAGES.get(dtek_status, messages.POWER_OFF_PLAN_DEFAULT)
        next_str = (
            messages.POWER_OFF_NEXT_CONNECTIVITY.format(time_str=next_connectivity_str)
            if next_connectivity_str
            else ""
        )

        return messages.POWER_OFF_MESSAGE.format(
            time_str=now.strftime("%H:%M"),
            dur_str=dur_str,
            plan_msg=plan_msg,
            next_str=next_str,
        )
