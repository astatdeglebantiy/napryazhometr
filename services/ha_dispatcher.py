import logging
from unittest import case

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
        self.cfg = config
        self.ha = ha_client
        self.schedule_pub = schedule_pub
        self.power_mon = power_mon
        self.voltage_mon = voltage_mon
        self.freq_mon = freq_mon

    async def sync_on_startup(self):
        """Catches up on any missed events while the bot was offline."""
        logger.info("Starting automatic startup synchronization...")

        # 1. Schedule Catch-Up: publish if calendar changed while bot was down
        try:
            await self.schedule_pub.check_and_publish(force=False)
        except Exception as e:
            logger.error("Failed to sync schedule on startup: %s", e)

        # 2. Power State Catch-Up: publish if power turned ON/OFF while bot was down
        try:
            await self.power_mon.sync_on_startup()
        except Exception as e:
            logger.error("Failed to sync power state on startup: %s", e)

        # 3. Voltage Telemetry Check: alert if voltage is currently abnormal
        try:
            p_state = await self.ha.get_entity_state(self.cfg.power_binary_sensor)
            power_is_on = (p_state.get("state") == "on") if p_state else False

            v_state = await self.ha.get_entity_state(self.cfg.voltage_sensor)
            if v_state and v_state.get("state") not in ("unknown", "unavailable"):
                v = float(v_state["state"])
                await self.voltage_mon.handle_voltage_change(v, power_is_on)
        except Exception as e:
            logger.error("Failed to sync voltage on startup: %s", e)

        # 4. Frequency Telemetry Check: alert if frequency is currently abnormal
        try:
            f_state = await self.ha.get_entity_state(self.cfg.frequency_sensor)
            if f_state and f_state.get("state") not in ("unknown", "unavailable"):
                hz = float(f_state["state"])
                await self.freq_mon.handle_frequency_change(hz, power_is_on)
        except Exception as e:
            logger.error("Failed to sync frequency on startup: %s", e)

        logger.info("Startup synchronization finished.")

    async def dispatch_event(self, data: dict):
        """Routes real-time WebSocket events from Home Assistant."""
        entity_id = data.get("entity_id")
        new_state = data.get("new_state")
        old_state = data.get("old_state")

        if not new_state or not old_state or new_state.get("state") in ("unknown", "unavailable"):
            return

        match entity_id:
            # 1. DTEK Schedule Update
            case self.cfg.dtek_schedule_updated_on:
                self.schedule_pub.trigger_update()

            # 2. Power State (ON / OFF)
            case self.cfg.power_binary_sensor:
                await self.power_mon.handle_power_state_change(
                    new_state=new_state["state"],
                    old_state=old_state["state"],
                )

            # 3. Voltage
            case self.cfg.voltage_sensor:
                try:
                    v = float(new_state["state"])
                except (ValueError, TypeError):
                    return

                p_state = await self.ha.get_entity_state(self.cfg.power_binary_sensor)
                power_is_on = (p_state.get("state") == "on") if p_state else False
                await self.voltage_mon.handle_voltage_change(v, power_is_on)

            # 4. Frequency
            case self.cfg.frequency_sensor:
                try:
                    hz = float(new_state["state"])
                except (ValueError, TypeError):
                    return

                p_state = await self.ha.get_entity_state(self.cfg.power_binary_sensor)
                power_is_on = (p_state.get("state") == "on") if p_state else False
                await self.freq_mon.handle_frequency_change(hz, power_is_on)
