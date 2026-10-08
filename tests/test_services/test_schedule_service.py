from datetime import date, datetime
import pytz
from models.schedule import CalendarEvent
from services.schedule_service import ScheduleService

def test_schedule_signature_calculation(schedule_service: ScheduleService, kyiv_tz):
    today = date(2026, 3, 4)
    planned = [
        CalendarEvent(
            start=kyiv_tz.localize(datetime(2026, 3, 4, 10, 0)),
            end=kyiv_tz.localize(datetime(2026, 3, 4, 12, 0))
        )
    ]
    scheduled = []
    # 10:00 = 600 минут, 12:00 = 720 минут
    sig = schedule_service.compute_signature(planned, scheduled, today)
    assert "600,720||2026-03-04" == sig

def test_build_day_timeline_no_events_today(schedule_service: ScheduleService):
    res = schedule_service.build_day_timeline([], date(2026, 3, 4), is_tomorrow=False)
    assert res == "💡 <i>Світло є (за графіком)</i>"

def test_build_day_timeline_no_events_tomorrow(schedule_service: ScheduleService):
    res = schedule_service.build_day_timeline([], date(2026, 3, 5), is_tomorrow=True)
    assert res == "❓ <i>Графік ще не опубліковано</i>"

def test_build_day_timeline_merging_adjacent_intervals(schedule_service: ScheduleService, kyiv_tz):
    target_date = date(2026, 3, 4)
    # Отключение с 08:00 до 12:00
    planned = [
        CalendarEvent(
            start=kyiv_tz.localize(datetime(2026, 3, 4, 8, 0)),
            end=kyiv_tz.localize(datetime(2026, 3, 4, 12, 0))
        )
    ]
    timeline_str = schedule_service.build_day_timeline(planned, target_date, is_tomorrow=False)
    expected = (
        "⬜ <code>00:00 — 08:00</code>\n"
        "⬛ <code>08:00 — 12:00</code>\n"
        "⬜ <code>12:00 — 24:00</code>"
    )
    assert timeline_str == expected
