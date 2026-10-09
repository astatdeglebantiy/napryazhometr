import asyncio
from dataclasses import dataclass
import logging
from typing import Callable
from aiogram import Bot

from config import Config
import messages
from models.power import FrequencyAlert
from storage.state_store import StateStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FrequencyRule:
    """Represents an alert rule for a specific grid frequency range."""
    condition: Callable[[float], bool]
    alert: FrequencyAlert
    suppressed_by: tuple[FrequencyAlert, ...]
    template: str


class FrequencyMonitor:
    # Declarative threshold rules ordered by priority
    ALERT_RULES = (
        FrequencyRule(
            condition=lambda hz: hz < 49.20,
            alert=FrequencyAlert.CRITICAL_LOW,
            suppressed_by=(FrequencyAlert.CRITICAL_LOW,),
            template=messages.FREQUENCY_CRITICAL_LOW,
        ),
        FrequencyRule(
            condition=lambda hz: 49.20 <= hz < 49.80,
            alert=FrequencyAlert.LOW,
            suppressed_by=(FrequencyAlert.LOW, FrequencyAlert.CRITICAL_LOW),
            template=messages.FREQUENCY_LOW,
        ),
        FrequencyRule(
            condition=lambda hz: hz > 50.25,
            alert=FrequencyAlert.HIGH,
            suppressed_by=(FrequencyAlert.HIGH,),
            template=messages.FREQUENCY_HIGH,
        ),
    )

    def __init__(self, bot: Bot, config: Config, store: StateStore):
        self.bot = bot
        self.cfg = config
        self.store = store
        self._restore_task: asyncio.Task | None = None

    def cancel_tasks(self):
        """Cancels any running stabilization tasks."""
        if self._restore_task and not self._restore_task.done():
            self._restore_task.cancel()

    async def handle_frequency_change(self, hz: float, is_power_on: bool):
        """Processes frequency changes and dispatches alerts or stabilization."""
        # Ignore sensor readings if power is disconnected or frequency is zero/invalid
        if not is_power_on or hz < 40.0:
            self.cancel_tasks()
            return

        # 1. Evaluate alert rules
        for rule in self.ALERT_RULES:
            if rule.condition(hz) and self.store.active_frequency_alert not in rule.suppressed_by:
                await self._apply_alert(rule, hz)
                return

        # 2. Check frequency stabilization range (49.90 - 50.10 Hz)
        if 49.90 <= hz <= 50.10:
            if self.store.active_frequency_alert != FrequencyAlert.NONE:
                self._schedule_restore(hz)
            return

        # 3. Cancel stabilization if frequency fluctuates outside the nominal band
        self.cancel_tasks()

    async def _apply_alert(self, rule: FrequencyRule, hz: float):
        """Persists the alert state and sends a notification."""
        self.cancel_tasks()
        self.store.active_frequency_alert = rule.alert
        self.store.save()
        await self._send(rule.template.format(hz=hz))

    def _schedule_restore(self, hz: float):
        """Starts a 30-second stabilization timer if not already active."""
        if not self._restore_task or self._restore_task.done():
            self._restore_task = asyncio.create_task(self._delayed_restore(hz))

    async def _delayed_restore(self, hz: float):
        """Waits for 30 seconds before declaring the grid synchronized and stabilized."""
        await asyncio.sleep(30)
        self.store.active_frequency_alert = FrequencyAlert.NONE
        self.store.save()
        await self._send(messages.FREQUENCY_RESTORED.format(hz=hz))

    async def _send(self, text: str):
        """Sends an HTML formatted message with optional environment prefix."""
        await self.bot.send_message(
            self.cfg.target_chat_id,
            self.cfg.msg_dev_prefix + text + self.cfg.msg_suffix,
        )
