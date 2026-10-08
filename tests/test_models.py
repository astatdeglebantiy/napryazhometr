from datetime import datetime
from models.power import PowerSnapshot, VoltageAlert
from models.schedule import CalendarEvent, PowerState, TimeInterval

def test_power_state_icons():
    assert PowerState.LIGHT_ON.icon == "⬜"
    assert PowerState.LIGHT_OFF.icon == "⬛"

def test_voltage_alert_enum():
    assert VoltageAlert.NONE.value == "none"
    assert VoltageAlert.LOW.value == "low"
    assert VoltageAlert.HIGH.value == "high"

def test_time_interval_formatting():
    interval_on = TimeInterval("00:00", "06:00", PowerState.LIGHT_ON)
    assert interval_on.to_str() == "⬜ <code>00:00 — 06:00</code>"

    interval_off = TimeInterval("06:00", "12:00", PowerState.LIGHT_OFF)
    assert interval_off.to_str() == "⬛ <code>06:00 — 12:00</code>"

def test_calendar_event_creation():
    start = datetime(2026, 3, 4, 10, 0)
    end = datetime(2026, 3, 4, 14, 0)
    event = CalendarEvent(start=start, end=end, summary="Вимкнення")
    assert event.start == start
    assert event.end == end
    assert event.summary == "Вимкнення"
