"""Zakazane obavijesti odvoza."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_NOTIFY_DAYS_BEFORE,
    CONF_NOTIFY_ENABLED,
    CONF_NOTIFY_ENTITIES,
    CONF_NOTIFY_TIME,
    DEFAULT_NOTIFY_DAYS_BEFORE,
    DEFAULT_NOTIFY_ENABLED,
    DEFAULT_NOTIFY_TIME,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .coordinator import MursEkomCoordinator
from .schedule import (
    format_date_hr,
    notify_target_date,
    parse_time,
)

_LOGGER = logging.getLogger(__name__)


def _notification_payload(item, when: str, location: str) -> tuple[str, str, str]:
    title = f"Odvoz smeća {when.lower()}"
    lines = [
        f"{when} ({format_date_hr(item.date)}) odvoze: {item.label}.",
        "Spremnik iznesite do 6:00 ujutro.",
    ]
    if "bulky" in item.types:
        lines.append("Glomazni otpad prijavite na 040/543-314 najkasnije 2 dana prije.")
    if "branches" in item.types:
        lines.append("Granje ostavite ispred kuće na dan odvoza.")
    lines.append(location)
    return title, "\n".join(lines), item.icon


class MursEkomNotifier:
    """Šalje notifikaciju u odabrano vrijeme, N dana prije odvoza."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: MursEkomCoordinator,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._unsub = None
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
        self._sent: dict[str, str] = {}

    async def async_start(self) -> None:
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self._sent = stored
        self._schedule()
        await self.async_maybe_send(catch_up=True)

    def _schedule(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

        hour, minute, second = parse_time(
            self.entry.options.get(CONF_NOTIFY_TIME, DEFAULT_NOTIFY_TIME)
        )

        @callback
        def _fire(_now) -> None:
            self.hass.async_create_task(self.async_maybe_send())

        self._unsub = async_track_time_change(
            self.hass,
            _fire,
            hour=hour,
            minute=minute,
            second=second,
        )

    async def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    def reload_schedule(self) -> None:
        self._schedule()

    def _options(self) -> tuple[bool, int, list[str]]:
        options = self.entry.options
        enabled = bool(options.get(CONF_NOTIFY_ENABLED, DEFAULT_NOTIFY_ENABLED))
        days_before = int(
            options.get(CONF_NOTIFY_DAYS_BEFORE, DEFAULT_NOTIFY_DAYS_BEFORE)
        )
        entities = list(options.get(CONF_NOTIFY_ENTITIES, []) or [])
        return enabled, days_before, entities

    async def async_maybe_send(self, catch_up: bool = False, force: bool = False) -> bool:
        enabled, days_before, entities = self._options()
        if not enabled and not force:
            return False

        now = dt_util.now()
        today = now.date()
        target = notify_target_date(today, days_before)
        item = self.coordinator.collection_on(target)
        if item is None:
            return False

        if catch_up and not force:
            hour, minute, _second = parse_time(
                self.entry.options.get(CONF_NOTIFY_TIME, DEFAULT_NOTIFY_TIME)
            )
            if (now.hour, now.minute) < (hour, minute):
                return False

        key = f"{today.isoformat()}_{item.date.isoformat()}"
        if not force and self._sent.get("last_key") == key:
            return False

        when = "Danas" if days_before == 0 else "Sutra" if days_before == 1 else f"Za {days_before} dana"
        title, message, icon = _notification_payload(
            item, when, self.coordinator.location_title
        )
        await self._async_deliver(title, message, icon, entities)
        self._sent = {"last_key": key}
        await self._store.async_save(self._sent)
        return True

    async def async_send_test(self) -> None:
        item = self.coordinator.data.get("next")
        entities = self.entry.options.get(CONF_NOTIFY_ENTITIES, []) or []
        if item is None:
            title = "Odvoz smeća"
            message = "Testna obavijest. Trenutačno nema predstojećeg termina u kalendaru."
            icon = "mdi:trash-can"
        else:
            title, message, icon = _notification_payload(
                item,
                "Sutra" if item.date != dt_util.now().date() else "Danas",
                self.coordinator.location_title,
            )
            message = f"TEST\n{message}"
        await self._async_deliver(title, message, icon, entities)

    async def _async_deliver(
        self,
        title: str,
        message: str,
        icon: str,
        entities: list[str],
    ) -> None:
        data = {
            "title": title,
            "message": message,
            "data": {
                "notification_icon": icon,
                "tag": "murs-ekom-odvoz",
                "channel": "Odvoz smeća",
                "color": "#2E7D32",
                "importance": "default",
                "push": {"sound": "default"},
                "group": "murs-ekom",
            },
        }
        if entities:
            for entity_id in entities:
                service = entity_id.split(".", 1)[-1]
                await self.hass.services.async_call(
                    "notify", service, data, blocking=False
                )
        else:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": title,
                    "message": message,
                    "notification_id": f"{DOMAIN}_odvoz",
                },
                blocking=False,
            )
        _LOGGER.info("Poslana obavijest odvoza: %s", title)
