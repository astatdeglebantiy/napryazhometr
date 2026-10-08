import asyncio
from datetime import datetime, timedelta
import json
import logging
from typing import Callable, Coroutine
import aiohttp
import pytz
from models.schedule import CalendarEvent

logger = logging.getLogger(__name__)


class HomeAssistantClient:
    def __init__(self, base_url: str, ws_url: str, token: str, tz_name: str = "Europe/Kyiv"):
        self.base_url = base_url.rstrip("/")
        self.ws_url = ws_url
        self.token = token
        self.tz = pytz.timezone(tz_name)
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._session: aiohttp.ClientSession | None = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers)
        return self._session

    async def get_entity_state(self, entity_id: str) -> dict | None:
        session = await self.get_session()
        async with session.get(f"{self.base_url}/api/states/{entity_id}") as resp:
            if resp.status == 200:
                return await resp.json()
        return None

    async def get_entity_history(
            self, entity_id: str, start_dt: datetime, end_dt: datetime
    ) -> list[dict]:
        """Запрашивает из Home Assistant реальную историю переключений датчика за период."""
        session = await self.get_session()
        url = f"{self.base_url}/api/history/period/{start_dt.isoformat()}"
        params = {
            "filter_entity_id": entity_id,
            "end_time": end_dt.isoformat(),
            "no_attributes": "1",
        }
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data[0] if data and len(data) > 0 else []
        except Exception:
            pass
        return []

    async def get_calendar_events(
        self, entity_id: str, start: datetime, duration_hours: int = 48
    ) -> list[CalendarEvent]:
        end = start + timedelta(hours=duration_hours)
        params = {"start": start.isoformat(), "end": end.isoformat()}
        session = await self.get_session()
        async with session.get(f"{self.base_url}/api/calendars/{entity_id}", params=params) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

        events = []
        for item in data:
            s_raw = item["start"].get("dateTime") or item["start"].get("date")
            e_raw = item["end"].get("dateTime") or item["end"].get("date")
            start_dt = datetime.fromisoformat(s_raw.replace("Z", "+00:00")).astimezone(self.tz)
            end_dt = datetime.fromisoformat(e_raw.replace("Z", "+00:00")).astimezone(self.tz)
            events.append(CalendarEvent(start=start_dt, end=end_dt, summary=item.get("summary", "")))
        return events

    async def listen_events(self, on_state_changed: Callable[[dict], Coroutine]):
        """Подписка на WebSocket Home Assistant для отслеживания state_changed событий."""
        while True:
            try:
                session = await self.get_session()
                async with session.ws_connect(self.ws_url) as ws:
                    auth_req = await ws.receive_json()
                    if auth_req.get("type") == "auth_required":
                        await ws.send_json({"type": "auth", "access_token": self.token})

                    auth_ok = await ws.receive_json()
                    if auth_ok.get("type") != "auth_ok":
                        logger.error("HA WS auth failed: %s", auth_ok)
                        await asyncio.sleep(5)
                        continue

                    logger.info("Успішно підключено до Home Assistant WebSocket")
                    await ws.send_json(
                        {"id": 1, "type": "subscribe_events", "event_type": "state_changed"}
                    )

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            payload = json.loads(msg.data)
                            if payload.get("type") == "event":
                                await on_state_changed(payload["event"]["data"])
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except Exception as e:
                logger.warning("Помилка з'єднання з HA WS: %s. Перепідключення через 5с...", e)
                await asyncio.sleep(5)
