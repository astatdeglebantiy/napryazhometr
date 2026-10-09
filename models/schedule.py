from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class PowerState(str, Enum):
    """Represents planned grid availability state."""
    LIGHT_ON = "LIGHT_ON"
    LIGHT_OFF = "LIGHT_OFF"

    @property
    def icon(self) -> str:
        """Visual status emoji indicator."""
        return "⬜" if self == PowerState.LIGHT_ON else "⬛"
        # idk
        #return "<tg-emoji emoji-id='5458789741136715070'>⬜</tg-emoji>" if self == PowerState.LIGHT_ON else "<tg-emoji emoji-id='5458733511424876694'>⬛</tg-emoji>"


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    """Represents a scheduled outage event from calendar providers."""
    start: datetime
    end: datetime
    summary: str = ""


@dataclass(frozen=True, slots=True)
class TimeInterval:
    """Represents a discrete time segment of the day with power state."""
    start_time: str
    end_time: str
    state: PowerState

    def to_str(self) -> str:
        """Formats the interval as an HTML string for Telegram messages."""
        return f"{self.state.icon} <code>{self.start_time} — {self.end_time}</code>"
