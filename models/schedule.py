from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class PowerState(Enum):
    LIGHT_ON = "LIGHT_ON"
    LIGHT_OFF = "LIGHT_OFF"

    @property
    def icon(self) -> str:
        return "⬜" if self == PowerState.LIGHT_ON else "⬛"


@dataclass(frozen=True)
class CalendarEvent:
    start: datetime
    end: datetime
    summary: str = ""


@dataclass(frozen=True)
class TimeInterval:
    start_time: str
    end_time: str
    state: PowerState

    def to_str(self) -> str:
        return f"{self.state.icon} <code>{self.start_time} — {self.end_time}</code>"
