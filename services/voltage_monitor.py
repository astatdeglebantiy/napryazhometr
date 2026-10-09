import asyncio
from dataclasses import dataclass
import logging
from typing import Callable
from aiogram import Bot

from config import Config
import messages
from models.power import VoltageAlert
from storage.state_store import StateStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VoltageRule:
    """Represents an alert rule for a specific voltage range."""
    condition: Callable[[float], bool]
    alert: VoltageAlert
    suppressed_by: tuple[VoltageAlert, ...]
    template: str


class VoltageMonitor:
    # Declarative threshold rules ordered by priority
    ALERT_RULES = (
        VoltageRule(
            condition=lambda v: v < 175,
            alert=VoltageAlert.CRITICAL_LOW,
            suppressed_by=(VoltageAlert.CRITICAL_LOW,),
            template=messages.VOLTAGE_CRITICAL_LOW,
        ),
        VoltageRule(
            condition=lambda v: 175 <= v < 195,
            alert=VoltageAlert.LOW,
            suppressed_by=(VoltageAlert.LOW, VoltageAlert.CRITICAL_LOW),
            template=messages.VOLTAGE_LOW,
        ),
        VoltageRule(
            condition=lambda v: 265 <= v < 320,
            alert=VoltageAlert.CRITICAL_HIGH,
            suppressed_by=(VoltageAlert.CRITICAL_HIGH,),
            template=messages.VOLTAGE_CRITICAL_HIGH,
        ),
        VoltageRule(
            condition=lambda v: 253 < v < 265,
            alert=VoltageAlert.HIGH,
            suppressed_by=(VoltageAlert.HIGH, VoltageAlert.CRITICAL_HIGH),
            template=messages.VOLTAGE_HIGH,
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

    async def handle_voltage_change(self, v: float, is_power_on: bool):
        """Processes voltage changes and dispatches alerts or stabilization."""
        if not is_power_on:
            self.cancel_tasks()
            return

        # 1. Evaluate alert rules
        for rule in self.ALERT_RULES:
            if rule.condition(v) and self.store.active_voltage_alert not in rule.suppressed_by:
                await self._apply_alert(rule, v)
                return

        # 2. Check voltage stabilization range (200 - 245 V)
        if 200 <= v <= 245:
            if self.store.active_voltage_alert != VoltageAlert.NONE:
                self._schedule_restore(v)
            return

        # 3. Cancel stabilization if voltage is outside normal range
        self.cancel_tasks()

    async def _apply_alert(self, rule: VoltageRule, v: float):
        """Persists the alert state and sends a notification."""
        self.cancel_tasks()
        self.store.active_voltage_alert = rule.alert
        self.store.save()
        await self._send(rule.template.format(v=v))

    def _schedule_restore(self, v: float):
        """Starts a 30-second stabilization timer if not already active."""
        if not self._restore_task or self._restore_task.done():
            self._restore_task = asyncio.create_task(self._delayed_restore(v))

    async def _delayed_restore(self, v: float):
        """Waits for 30 seconds before declaring the grid stabilized."""
        await asyncio.sleep(30)
        self.store.active_voltage_alert = VoltageAlert.NONE
        self.store.save()
        await self._send(messages.VOLTAGE_RESTORED.format(v=v))

    async def _send(self, text: str):
        """Sends an HTML formatted message with optional prefix."""
        await self.bot.send_message(
            self.cfg.target_chat_id,
            self.cfg.msg_prefix + text,
        )
