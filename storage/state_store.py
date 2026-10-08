import json
from pathlib import Path
from models.power import FrequencyAlert, VoltageAlert


class StateStore:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.last_power_on_ts: float | None = None
        self.last_power_off_ts: float | None = None
        self.active_voltage_alert: VoltageAlert = VoltageAlert.NONE
        self.active_frequency_alert: FrequencyAlert = FrequencyAlert.NONE  # <-- Новое поле
        self.last_schedule_hash: str = ""
        self._load()

    def _load(self):
        if self.file_path.exists():
            try:
                data = json.loads(self.file_path.read_text(encoding="utf-8"))
                self.last_power_on_ts = data.get("last_power_on_ts")
                self.last_power_off_ts = data.get("last_power_off_ts")
                self.active_voltage_alert = VoltageAlert(data.get("active_voltage_alert", "none"))
                self.active_frequency_alert = FrequencyAlert(data.get("active_frequency_alert", "none"))
                self.last_schedule_hash = data.get("last_schedule_hash", "")
            except Exception:
                pass

    def save(self):
        data = {
            "last_power_on_ts": self.last_power_on_ts,
            "last_power_off_ts": self.last_power_off_ts,
            "active_voltage_alert": self.active_voltage_alert.value,
            "active_frequency_alert": self.active_frequency_alert.value,
            "last_schedule_hash": self.last_schedule_hash,
        }
        self.file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
