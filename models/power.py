from dataclasses import dataclass
from enum import Enum


class VoltageAlert(str, Enum):
    """Grid voltage alert severity levels."""
    NONE = "none"
    LOW = "low"
    CRITICAL_LOW = "critical_low"
    HIGH = "high"
    CRITICAL_HIGH = "critical_high"


class FrequencyAlert(str, Enum):
    """Grid frequency alert severity levels."""
    NONE = "none"
    LOW = "low"
    CRITICAL_LOW = "critical_low"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class PowerSnapshot:
    """Immutable point-in-time snapshot of grid and telemetry status."""
    is_on: bool
    voltage: float
    dtek_status: str
    frequency: float | None = None
    last_power_on_ts: float | None = None
    last_power_off_ts: float | None = None
