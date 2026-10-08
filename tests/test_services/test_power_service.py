import pytest
from datetime import datetime
from freezegun import freeze_time
from models.power import PowerSnapshot
from services.power_service import PowerService

def test_format_duration(power_service: PowerService):
    assert power_service.format_duration(0) == "00:00:00"
    assert power_service.format_duration(59) == "00:00:59"
    assert power_service.format_duration(3600) == "01:00:00"
    assert power_service.format_duration(3665) == "01:01:05"
    assert power_service.format_duration(-10) == "00:00:00"

@freeze_time("2026-03-04 12:00:00")
def test_build_popup_message_power_on_plan(power_service: PowerService):
    snapshot = PowerSnapshot(
        is_on=True,
        voltage=224.5,
        dtek_status="normal",
        last_power_on_ts=datetime(2026, 3, 4, 10, 30, 0).timestamp()
    )
    msg = power_service.build_popup_message(snapshot)
    assert "💡 Є • 01:30:00" in msg
    assert "✅ План" in msg
    assert "⚡️ 224.5V" in msg
    assert "⚠️" not in msg

@freeze_time("2026-03-04 12:00:00")
def test_build_popup_message_power_off_out_of_plan_and_low_voltage(power_service: PowerService):
    snapshot = PowerSnapshot(
        is_on=False,
        voltage=180.2,
        dtek_status="normal",  # По ДТЭК свет должен быть, но его нет -> вне плана
        last_power_off_ts=datetime(2026, 3, 4, 11, 45, 0).timestamp()
    )
    msg = power_service.build_popup_message(snapshot)
    assert "🔌 Нема • 00:15:00" in msg
    assert "🎰 Поза планом" in msg
    assert "⚡️ 180.2V ⚠️" in msg

@freeze_time("2026-03-04 12:00:00")
def test_build_power_on_message_lucky(power_service: PowerService, state_store):
    state_store.last_power_off_ts = datetime(2026, 3, 4, 9, 0, 0).timestamp()
    msg = power_service.build_power_on_message(
        voltage=228.1,
        dtek_status="planned_outage",
        next_outage_str="16:00"
    )
    assert "🟢 СВІТЛО З'ЯВИЛОСЯ" in msg
    assert "⚡️ Напруга: 228.1 V" in msg
    assert "⏳ Світла не було: 03:00:00" in msg
    assert "🎰 <b>Нам пощастило!</b>" in msg
    assert "🌚 Наступне відключення: 16:00" in msg

@freeze_time("2026-03-04 12:00:00")
def test_build_power_off_message_scheduled(power_service: PowerService, state_store):
    state_store.last_power_on_ts = datetime(2026, 3, 4, 8, 0, 0).timestamp()
    msg = power_service.build_power_off_message(
        dtek_status="planned_outage",
        next_connectivity_str="15:00"
    )
    assert "🔴 СВІТЛО ВИМКНУЛИ" in msg
    assert "💡 Світло було: 04:00:00" in msg
    assert "✅ <b>Планове відключення.</b>" in msg
    assert "💡 Очікуване ввімкнення: 15:00" in msg
