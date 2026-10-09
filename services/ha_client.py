import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
import json
import logging
import aiohttp
import pytz

from models.schedule import CalendarEvent

logger = logging.getLogger(__name__)


class HomeAssistantClient:
    """Asynchronous client for Home Assistant REST and WebSocket APIs."""

    def __init__(self, base_url: str, ws_url: str, token: str, tz_name: str = "Europe/Kyiv"):
        self.base_url = base_url.rstrip("/")
        self.ws_url = ws_url
        self.token = token.strip()
        self.tz = pytz.timezone(tz_name)
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        self._session: aiohttp.ClientSession | None = None

    async def get_session(self) -> aiohttp.ClientSession:
        """Returns or lazily creates an active aiohttp client session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(headers=self.headers, timeout=timeout)
        return self._session

    async def get_entity_state(self, entity_id: str) -> dict | None:
        """Fetches the current state payload for a given Home Assistant entity."""
        session = await self.get_session()
        try:
            async with session.get(f"{self.base_url}/api/states/{entity_id}") as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.debug("Failed to fetch state for %s: %s", entity_id, e)
        return None

    async def get_entity_history(
        self, entity_id: str, start_dt: datetime, end_dt: datetime
    ) -> list[dict]:
        """Fetches historical state changes for a given entity from Home Assistant recorder."""
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
        except Exception as e:
            logger.warning("Failed to fetch history for %s: %s", entity_id, e)
        return []

    async def get_calendar_events(
        self, entity_id: str, start: datetime, duration_hours: int = 48
    ) -> list[CalendarEvent]:
        """Fetches scheduled events for a specific calendar entity within a time window."""
        end = start + timedelta(hours=duration_hours)
        params = {"start": start.isoformat(), "end": end.isoformat()}
        session = await self.get_session()

        try:
            async with session.get(f"{self.base_url}/api/calendars/{entity_id}", params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
        except Exception as e:
            logger.warning("Failed to fetch calendar events for %s: %s", entity_id, e)
            return []

        events: list[CalendarEvent] = []
        for item in data:
            s_raw = item["start"].get("dateTime") or item["start"].get("date")
            e_raw = item["end"].get("dateTime") or item["end"].get("date")

            start_dt = self._parse_iso_datetime(s_raw)
            end_dt = self._parse_iso_datetime(e_raw)

            events.append(CalendarEvent(start=start_dt, end=end_dt, summary=item.get("summary", "")))
        return events

    async def listen_events(self, on_state_changed: Callable[[dict], Awaitable[None]]):
        """Subscribes to Home Assistant WebSocket state_changed event stream with auto-reconnect."""
        while True:
            try:
                session = await self.get_session()
                # heartbeat=30.0 detects broken TCP connections and triggers reconnects
                async with session.ws_connect(self.ws_url, heartbeat=30.0) as ws:
                    auth_req = await ws.receive_json()
                    if auth_req.get("type") == "auth_required":
                        await ws.send_json({"type": "auth", "access_token": self.token})

                    auth_ok = await ws.receive_json()
                    if auth_ok.get("type") != "auth_ok":
                        logger.error("Home Assistant WebSocket auth failed: %s", auth_ok)
                        await asyncio.sleep(5)
                        continue

                    logger.info("Successfully connected to Home Assistant WebSocket.")
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
                logger.warning("Home Assistant WebSocket connection error: %s. Reconnecting in 5s...", e)
                await asyncio.sleep(5)

    async def close(self):
        """Gracefully closes underlying aiohttp client session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _parse_iso_datetime(self, raw_str: str) -> datetime:
        """Parses ISO timestamp ensuring timezone awareness."""
        dt = datetime.fromisoformat(raw_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = self.tz.localize(dt)
        return dt.astimezone(self.tz)
