"""Koordinator rasporeda odvoza."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CALENDAR_STORAGE_VERSION,
    CONF_LOCATION,
    CONF_PULL_INTERVAL_DAYS,
    DEFAULT_PULL_INTERVAL_DAYS,
    DOMAIN,
)
from .i18n import collection_label, resolve_language, text as i18n_text, waste_name
from .source import (
    ARCHIVE_URL,
    API_URL,
    USER_AGENT,
    fallback_calendar,
    parse_calendar_html,
    parse_locations,
)
from .schedule import (
    TYPE_ORDER,
    Collection,
    collection_on_from,
    collections_from_events,
    last_from,
    next_from,
    recycle_yard_info,
    upcoming_from,
)

_LOGGER = logging.getLogger(__name__)

MURS_EKOM_URL = "https://murs-ekom.hr/"


class MursEkomCoordinator(DataUpdateCoordinator[dict]):
    """Povlači kalendar i izračunava sljedeće odvoze."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )
        self.entry = entry
        self._store = Store(
            hass, CALENDAR_STORAGE_VERSION, f"{DOMAIN}_calendar_{entry.entry_id}"
        )
        self._calendar: dict | None = None
        self._force_remote = False
        self.locations: list[dict[str, str]] = []

    @property
    def location_id(self) -> str:
        return str(
            self.entry.options.get(CONF_LOCATION)
            or self.entry.data.get(CONF_LOCATION)
        )

    @property
    def location_title(self) -> str:
        if self._calendar and self._calendar.get("name"):
            return self._calendar["name"]
        for item in self.locations:
            if item["id"] == self.location_id:
                return item["name"]
        return self.location_id

    @property
    def language(self) -> str:
        return resolve_language(self.hass, self.entry)

    def text(self, key: str, **kwargs) -> str:
        return i18n_text(self.language, key, **kwargs)

    def waste_label(self, waste_type: str) -> str:
        return waste_name(self.language, waste_type)

    def types_label(self, types) -> str:
        return collection_label(self.language, types)

    @property
    def source_url(self) -> str:
        return MURS_EKOM_URL

    @property
    def items(self) -> list[Collection]:
        if not self._calendar:
            return []
        return collections_from_events(self._calendar.get("events", []))

    def pull_days(self) -> int:
        return int(
            self.entry.options.get(
                CONF_PULL_INTERVAL_DAYS, DEFAULT_PULL_INTERVAL_DAYS
            )
        )

    def collection_on(self, day) -> Collection | None:
        return collection_on_from(self.items, day)

    async def async_config_entry_first_refresh(self) -> None:
        stored = await self._store.async_load()
        if isinstance(stored, dict) and stored.get("events"):
            self._calendar = stored
        await super().async_config_entry_first_refresh()

    async def async_refresh_remote(self) -> None:
        self._force_remote = True
        await self.async_request_refresh()

    def _is_stale(self) -> bool:
        if not self._calendar or not self._calendar.get("events"):
            return True
        if self._calendar.get("id") != self.location_id:
            return True
        force_at = self.entry.options.get("force_fetch_at")
        fetched = self._calendar.get("fetched_at")
        if force_at and (not fetched or force_at > fetched):
            return True
        if not fetched:
            return True
        fetched_dt = datetime.fromisoformat(fetched)
        now = dt_util.now()
        if fetched_dt.tzinfo is None:
            fetched_dt = fetched_dt.replace(tzinfo=now.tzinfo)
        return now - fetched_dt >= timedelta(days=self.pull_days())

    async def _async_update_data(self) -> dict:
        if self._force_remote or self._is_stale():
            try:
                await self._fetch_remote()
            except Exception as err:
                if not self._calendar or not self._calendar.get("events"):
                    fallback = fallback_calendar(self.location_id)
                    if fallback is None:
                        raise UpdateFailed(f"Kalendar nije dostupan: {err}") from err
                    self._calendar = fallback
                    _LOGGER.warning(
                        "Udaljeni kalendar nije dostupan, korišten lokalni: %s", err
                    )
                else:
                    _LOGGER.warning("Osvježavanje kalendara nije uspjelo, ostaje cache: %s", err)
            finally:
                self._force_remote = False
        return self._build_state()

    async def _fetch_remote(self) -> None:
        session = async_get_clientsession(self.hass)
        headers = {"User-Agent": USER_AGENT}
        async with session.get(
            f"{API_URL}?per_page=100&_fields=id,slug,link,title",
            headers=headers,
            timeout=30,
        ) as response:
            response.raise_for_status()
            payload = await response.json()
        self.locations = parse_locations(payload)
        location = next(
            (item for item in self.locations if item["id"] == self.location_id),
            None,
        )
        if location is None:
            location = {
                "id": self.location_id,
                "name": self.location_id,
                "url": f"{ARCHIVE_URL}{self.location_id}/",
            }
        async with session.get(location["url"], headers=headers, timeout=30) as response:
            response.raise_for_status()
            html = await response.text()
        parsed = parse_calendar_html(
            html, url=location["url"], slug=location["id"]
        )
        if not parsed["events"]:
            raise UpdateFailed("Kalendar je prazan")
        parsed["fetched_at"] = dt_util.now().isoformat()
        parsed["source"] = "remote"
        self._calendar = parsed
        await self._store.async_save(parsed)
        _LOGGER.info(
            "Povučen kalendar %s (%s termina)",
            parsed["name"],
            len(parsed["events"]),
        )

    def _build_state(self) -> dict:
        today = dt_util.now().date()
        items = self.items
        per_type: dict[str, Collection | None] = {
            waste_type: next_from(items, today, waste_type=waste_type)
            for waste_type in TYPE_ORDER
        }
        last_type: dict[str, Collection | None] = {
            waste_type: last_from(items, today, waste_type=waste_type)
            for waste_type in TYPE_ORDER
        }
        bundled = fallback_calendar(self.location_id)
        if bundled and bundled.get("events"):
            bundled_items = collections_from_events(bundled["events"])
            for waste_type in TYPE_ORDER:
                if last_type[waste_type] is None:
                    last_type[waste_type] = last_from(
                        bundled_items, today, waste_type=waste_type
                    )
        return {
            "today": today,
            "next": next_from(items, today),
            "today_item": collection_on_from(items, today),
            "upcoming": upcoming_from(items, today),
            "all": items,
            "per_type": per_type,
            "last_type": last_type,
            "yard": recycle_yard_info(),
            "last_pull": self._calendar.get("fetched_at") if self._calendar else None,
            "source": self._calendar.get("source") if self._calendar else None,
            "location": self.location_title,
            "pull_days": self.pull_days(),
        }
