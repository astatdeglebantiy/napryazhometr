import asyncio
from datetime import datetime
import pytz
from config import Config
from models.power import PowerSnapshot, VoltageAlert
from storage.state_store import StateStore


class PowerService:
    def __init__(self, config: Config, store: StateStore):
        self.cfg = config
        self.store = store
        self.tz = pytz.timezone(config.timezone)

        # Задачи отложенных проверок (для таймеров 'for: 15s' и 'for: 30s')
        self._power_on_task: asyncio.Task | None = None
        self._voltage_restore_task: asyncio.Task | None = None

    def format_duration(self, seconds: int) -> str:
        s = max(0, seconds)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"{h:02d} год {m:02d} хв"

    def build_popup_message(self, snapshot: PowerSnapshot) -> str:
        """Формирует текст для Alert-попапа (/check_status)."""
        now_ts = datetime.now().timestamp()
        target_ts = snapshot.last_power_on_ts if snapshot.is_on else snapshot.last_power_off_ts
        dur_str = "00:00:00"
        if target_ts:
            dur_str = self.format_duration(int(now_ts - target_ts))

        is_planned = (snapshot.is_on and snapshot.dtek_status == "normal") or (
                not snapshot.is_on and snapshot.dtek_status != "normal"
        )
        plan_badge = "✅ План" if is_planned else "🎰 Поза планом"
        state_icon = "💡 Є" if snapshot.is_on else "🔌 Нема"

        volt_warn = " ⚠️" if 50 < snapshot.voltage < 190 else ""

        # Добавляем частоту, если свет есть
        freq_str = f" • {snapshot.frequency:.1f}Hz" if snapshot.frequency and snapshot.is_on else ""
        #freq_str = f" • 49.9Hz"

        return (
            f"{state_icon} • {dur_str}\n"
            f"{plan_badge}\n"
            f"⚡️ {snapshot.voltage:.1f}V{volt_warn}{freq_str}"
            #f"⚡️ 175.7V ⚠️{freq_str}"
        )

    def build_power_on_message(
        self, voltage: float, dtek_status: str, next_outage_str: str | None
    ) -> str:
        now = datetime.now(self.tz)
        dur_str = ""
        if self.store.last_power_off_ts:
            elapsed = int(now.timestamp() - self.store.last_power_off_ts)
            dur_str = f"\n⏳ Світла не було {self.format_duration(elapsed)}"

        if dtek_status == "planned_outage":
            plan_msg = "🎰 <b>Нам пощастило!</b> Світло дали, хоча за графіком відключення."
        elif dtek_status == "normal":
            plan_msg = "✅ <b>Все за планом.</b> Включення співпадає з графіком."
        else:
            plan_msg = "⚠️ <b>Світло з'явилося!</b> (Ймовірно завершення аварійних)."

        next_str = f"\n🌚 Наступне відключення: {next_outage_str}" if next_outage_str else ""

        return (
            f"<b>🟢 СВІТЛО З'ЯВИЛОСЯ</b>\n\n"
            f"⚡️ Напруга: {voltage:.1f} V\n"
            f"🕘 Світло з'явилося о {now.strftime("%H год %M хв")}{dur_str}\n\n"
            f"{plan_msg}{next_str}\n\n"
            f"⏳ <i>Зачекайте 3-5 хв для стабілізації системи.</i>"
        )

    def build_power_off_message(
        self, dtek_status: str, next_connectivity_str: str | None
    ) -> str:
        now = datetime.now(self.tz)
        dur_str = ""
        if self.store.last_power_on_ts:
            elapsed = int(now.timestamp() - self.store.last_power_on_ts)
            dur_str = f"\n💡 Світло було: {self.format_duration(elapsed)}"

        if dtek_status == "normal":
            plan_msg = "🤬 Світло зникло, <b>хоча за графіком має бути.</b>"
        elif dtek_status == "planned_outage":
            plan_msg = "✅ <b>Планове відключення.</b> Все чітко за розкладом."
        else:
            plan_msg = "⚠️ <b>Аварійне/Екстрене відключення.</b>"

        next_str = f"\n💡 Очікуване ввімкнення: {next_connectivity_str}" if next_connectivity_str else ""

        return (
            f"<b>🔴 СВІТЛО ВИМКНУЛИ</b>\n\n"
            f"🕒 Світло зникло о {now.strftime("%H год %M хв")}{dur_str}\n\n"
            f"{plan_msg}{next_str}\n\n"
            f"🔋 Переходимо на автономне живлення.\n"
            f"<i>Бот моніторить мережу 24/7</i>"
        )

    def cancel_tasks(self):
        if self._power_on_task and not self._power_on_task.done():
            self._power_on_task.cancel()
        if self._voltage_restore_task and not self._voltage_restore_task.done():
            self._voltage_restore_task.cancel()
