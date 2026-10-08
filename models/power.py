from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class VoltageAlert(str, Enum):
    NONE = "none"
    LOW = "low"
    CRITICAL_LOW = "critical_low"
    HIGH = "high"
    CRITICAL_HIGH = "critical_high"

class FrequencyAlert(str, Enum):
    NONE = "none"
    LOW = "low"
    CRITICAL_LOW = "critical_low"
    HIGH = "high"


@dataclass
class PowerSnapshot:
    is_on: bool
    voltage: float
    dtek_status: str
    frequency: float | None = None
    last_power_on_ts: float | None = None
    last_power_off_ts: float | None = None
