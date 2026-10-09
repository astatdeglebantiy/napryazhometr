from enum import Enum
import json
import logging
from pathlib import Path
from typing import Type, TypeVar

from models.power import FrequencyAlert, VoltageAlert

logger = logging.getLogger(__name__)

E = TypeVar("E", bound=Enum)


class StateStore:
    """Thread-safe persistent JSON-backed storage for bot runtime state."""

    def __init__(self, file_path: Path | str):
        self.file_path = Path(file_path)
        self.last_power_on_ts: float | None = None
        self.last_power_off_ts: float | None = None
        self.active_voltage_alert: VoltageAlert = VoltageAlert.NONE
        self.active_frequency_alert: FrequencyAlert = FrequencyAlert.NONE
        self.last_schedule_hash: str = ""
        self._load()

    def _load(self):
        """Loads state from persistent file with safe fallbacks on parsing failure."""
        if not self.file_path.exists():
            return

        try:
            content = self.file_path.read_text(encoding="utf-8").strip()
            if not content:
                return

            data = json.loads(content)
            self.last_power_on_ts = data.get("last_power_on_ts")
            self.last_power_off_ts = data.get("last_power_off_ts")
            self.active_voltage_alert = self._safe_enum(
                VoltageAlert, data.get("active_voltage_alert"), VoltageAlert.NONE
            )
            self.active_frequency_alert = self._safe_enum(
                FrequencyAlert, data.get("active_frequency_alert"), FrequencyAlert.NONE
            )
            self.last_schedule_hash = data.get("last_schedule_hash", "")
        except Exception as e:
            logger.warning(
                "Could not load state file %s (%s). Using initial defaults.",
                self.file_path,
                e,
            )

    def save(self):
        """Atomically saves state to disk to prevent corruption on unexpected power cuts."""
        data = {
            "last_power_on_ts": self.last_power_on_ts,
            "last_power_off_ts": self.last_power_off_ts,
            "active_voltage_alert": self.active_voltage_alert.value,
            "active_frequency_alert": self.active_frequency_alert.value,
            "last_schedule_hash": self.last_schedule_hash,
        }

        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.file_path.with_suffix(".tmp")

        try:
            temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temp_file.replace(self.file_path)  # Atomic rename on POSIX/Linux
        except Exception as e:
            logger.error("Failed to write state file %s: %s", self.file_path, e)
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass

    @staticmethod
    def _safe_enum(enum_cls: Type[E], value: str | None, default: E) -> E:
        """Safely parses enum value falling back to default without discarding entire store."""
        try:
            return enum_cls(value)  # type: ignore
        except (ValueError, KeyError, TypeError):
            return default
