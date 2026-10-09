import logging
from config import Config
from services.frequency_monitor import FrequencyMonitor
from services.ha_client import HomeAssistantClient
from services.power_monitor import PowerMonitor
from services.schedule_publisher import SchedulePublisher
from services.voltage_monitor import VoltageMonitor

logger = logging.getLogger(__name__)


class HomeAssistantDispatcher:
    def __init__(
        self,
        config: Config,
        ha_client: HomeAssistantClient,
        schedule_pub: SchedulePublisher,
        power_mon: PowerMonitor,
        voltage_mon: VoltageMonitor,
        freq_mon: FrequencyMonitor,
    ):
        self.config = config
        self.ha = ha_client
        self.schedule_pub = schedule_pub
        self.power_mon = power_mon
        self.voltage_mon = voltage_mon
        self.freq_mon = freq_mon

    async def dispatch_event(self, data: dict):
        entity_id = data.get("entity_id")
        new_state = data.get("new_state")
        old_state = data.get("old_state")

        if not new_state or not old_state or new_state.get("state") in ("unknown", "unavailable"):
            return

        match entity_id:

            case self.config.dtek_schedule_updated_on:
                self.schedule_pub.trigger_update()

            case self.config.power_binary_sensor:
                await self.power_mon.handle_power_state_change(
                    new_state=new_state["state"],
                    old_state=old_state["state"],
                )

            case self.config.voltage_sensor:
                try:
                    v = float(new_state["state"])
                except (ValueError, TypeError):
                    return

                p_state = await self.ha.get_entity_state(self.config.power_binary_sensor)
                power_is_on = (p_state.get("state") == "on") if p_state else False
                await self.voltage_mon.handle_voltage_change(v, power_is_on)

            case self.config.frequency_sensor:
                try:
                    hz = float(new_state["state"])
                except (ValueError, TypeError):
                    return

                p_state = await self.ha.get_entity_state(self.config.power_binary_sensor)
                power_is_on = (p_state.get("state") == "on") if p_state else False
                await self.freq_mon.handle_frequency_change(hz, power_is_on)
