from datetime import date, datetime, timedelta
import pytz
from models.schedule import CalendarEvent, PowerState, TimeInterval


class ScheduleService:
    def __init__(self, tz_name: str = "Europe/Kyiv"):
        self.tz = pytz.timezone(tz_name)

    def _get_day_start(self, d: date) -> datetime:
        """Безопасная локализация начала суток в pytz без сдвига LMT (+02:02)."""
        return self.tz.localize(datetime.combine(d, datetime.min.time()))

    def compute_signature(
        self, planned: list[CalendarEvent], scheduled: list[CalendarEvent], today: date
    ) -> str:
        today_start = self._get_day_start(today)
        t0 = int(today_start.timestamp())
        items = []
        for e in planned:
            s_min = (int(e.start.timestamp()) - t0) // 60
            f_min = (int(e.end.timestamp()) - t0) // 60
            if f_min > 0 and s_min < 2880:
                items.append(f"{s_min},{f_min}")

        all_events = planned + scheduled
        default_horizon = self.tz.localize(datetime(2000, 1, 1))
        horizon = max((e.end for e in all_events), default=default_horizon).strftime("%Y-%m-%d")
        return f"{'|'.join(items)}||{horizon}"

    def build_day_timeline(
        self, events: list[CalendarEvent], target_date: date, is_tomorrow: bool
    ) -> str:
        day_start = self._get_day_start(target_date)
        day_end = day_start + timedelta(days=1)
        day_events = [e for e in events if e.start < day_end and e.end > day_start]

        if not day_events:
            return "❓ <i>Графік ще не опубліковано</i>" if is_tomorrow else "💡 <i>Світло є (за графіком)</i>"

        pts = {0, 1440}
        for e in day_events:
            s = max(day_start, e.start)
            f = min(day_end, e.end)
            pts.add(int((s - day_start).total_seconds() // 60))
            pts.add(int((f - day_start).total_seconds() // 60))

        sorted_pts = sorted(pts)
        intervals: list[TimeInterval] = []

        for i in range(len(sorted_pts) - 1):
            p1, p2 = sorted_pts[i], sorted_pts[i + 1]
            mid = day_start + timedelta(minutes=(p1 + p2) / 2)
            is_off = any(e.start <= mid < e.end for e in day_events)
            intervals.append(
                TimeInterval(
                    start_time=self._min_to_str(p1),
                    end_time=self._min_to_str(p2),
                    state=PowerState.LIGHT_OFF if is_off else PowerState.LIGHT_ON,
                )
            )

        merged = []
        curr = intervals[0]
        for nxt in intervals[1:]:
            if nxt.state == curr.state:
                curr = TimeInterval(curr.start_time, nxt.end_time, curr.state)
            else:
                merged.append(curr)
                curr = nxt
        merged.append(curr)

        return "\n".join(i.to_str() for i in merged)

    @staticmethod
    def _min_to_str(m: int) -> str:
        return "24:00" if m == 1440 else f"{m // 60:02d}:{m % 60:02d}"
