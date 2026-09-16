"""Zakazane obavijesti odvoza."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_NOTIFY_DAYS_BEFORE,
    CONF_NOTIFY_ENABLED,
    CONF_NOTIFY_ENTITIES,
    CONF_NOTIFY_TIME,
    CONF_TODO_ENABLED,
    DEFAULT_NOTIFY_DAYS_BEFORE,
    DEFAULT_NOTIFY_ENABLED,
    DEFAULT_NOTIFY_TIME,
    DEFAULT_TODO_ENABLED,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .coordinator import MursEkomCoordinator
from .i18n import format_date, when_text
from .schedule import (
    days_until,
    notify_target_date,
    parse_time,
)
from .todo_list import async_add_collection_item, async_ensure_smece_list

_LOGGER = logging.getLogger(__name__)


def _payload(coordinator: MursEkomCoordinator, item, days_before: int | None = None) -> tuple[str, str, str]:
    today = dt_util.now().date()
    days = days_before if days_before is not None else days_until(item, today)
    when = when_text(coordinator.language, days)
    title = coordinator.text("notify_title", when=when.lower())
    lines = [
        coordinator.text(
            "notify_body",
            when=when,
            date=format_date(item.date),
            types=coordinator.types_label(item.types),
        ),
        coordinator.text("prepare"),
    ]
    if "bulky" in item.types:
        lines.append(coordinator.text("bulky_note"))
    if "branches" in item.types:
        lines.append(coordinator.text("branches_note"))
    lines.append(coordinator.location_title)
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
        if self._todo_enabled():
            try:
                await async_ensure_smece_list(self.hass)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("To-do lista Smeće nije spremna")
        try:
            await self.async_maybe_send(catch_up=True)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Catch-up obavijest nije uspjela")

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

    def _todo_enabled(self) -> bool:
        return bool(self.entry.options.get(CONF_TODO_ENABLED, DEFAULT_TODO_ENABLED))

    def _options(self) -> tuple[bool, bool, int, list[str]]:
        options = self.entry.options
        notify_on = bool(options.get(CONF_NOTIFY_ENABLED, DEFAULT_NOTIFY_ENABLED))
        todo_on = bool(options.get(CONF_TODO_ENABLED, DEFAULT_TODO_ENABLED))
        days_before = int(
            options.get(CONF_NOTIFY_DAYS_BEFORE, DEFAULT_NOTIFY_DAYS_BEFORE)
        )
        entities = list(options.get(CONF_NOTIFY_ENTITIES, []) or [])
        return notify_on, todo_on, days_before, entities

    async def async_maybe_send(self, catch_up: bool = False, force: bool = False) -> bool:
        notify_on, todo_on, days_before, entities = self._options()
        if not notify_on and not todo_on and not force:
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

        when_days = days_before
        title, message, icon = _payload(self.coordinator, item, when_days)
        delivered = False
        if notify_on or force:
            await self._async_deliver(title, message, icon, entities)
            delivered = True
        if todo_on:
            delivered = await self._async_add_todo(item, message) or delivered
        if delivered and not force:
            self._sent = {"last_key": key}
            await self._store.async_save(self._sent)
        return delivered

    async def async_send_test(self) -> None:
        item = self.coordinator.data.get("next")
        entities = self.entry.options.get(CONF_NOTIFY_ENTITIES, []) or []
        if item is None:
            title = self.coordinator.text("device_name")
            message = self.coordinator.text("notify_empty")
            icon = "mdi:trash-can"
        else:
            title, message, icon = _payload(self.coordinator, item)
            message = f"{self.coordinator.text('notify_test')}\n{message}"
        await self._async_deliver(title, message, icon, entities)
        if self._todo_enabled() and item is not None:
            await self._async_add_todo(
                item, message, summary_prefix=self.coordinator.text("notify_test")
            )

    async def _async_add_todo(
        self, item, message: str, summary_prefix: str | None = None
    ) -> bool:
        summary = self.coordinator.types_label(item.types)
        if summary_prefix:
            summary = f"{summary_prefix}: {summary}"
        return await async_add_collection_item(
            self.hass,
            summary=summary,
            due_date=item.date.isoformat(),
            description=message,
        )

    async def _async_deliver(
        self,
        title: str,
        message: str,
        icon: str,
        entities: list[str],
    ) -> None:
        extra = {
            "notification_icon": icon,
            "tag": "murs-ekom-odvoz",
            "channel": self.coordinator.text("device_name"),
            "color": "#2E7D32",
            "importance": "default",
            "push": {"sound": "default"},
            "group": "murs-ekom",
        }
        sent = False
        for entity_id in entities:
            if await self._async_notify_entity(entity_id, title, message, extra):
                sent = True
        if not entities or not sent:
            await self._async_persistent(title, message)
        if sent or not entities:
            _LOGGER.info("Poslana obavijest odvoza: %s", title)

    async def _async_notify_entity(
        self,
        entity_id: str,
        title: str,
        message: str,
        extra: dict,
    ) -> bool:
        service = entity_id.split(".", 1)[-1] if "." in entity_id else entity_id
        try:
            if self.hass.services.has_service("notify", service):
                await self.hass.services.async_call(
                    "notify",
                    service,
                    {"title": title, "message": message, "data": extra},
                    blocking=False,
                )
                return True
            if self.hass.services.has_service("notify", "send_message"):
                await self.hass.services.async_call(
                    "notify",
                    "send_message",
                    {"title": title, "message": message},
                    blocking=False,
                    target={"entity_id": entity_id},
                )
                return True
        except HomeAssistantError as err:
            _LOGGER.warning("Obavijest na %s nije uspjela: %s", entity_id, err)
            return False
        _LOGGER.warning(
            "Nema notify akcije za %s. Odaberi Companion entitet, npr. notify.mobile_app_...",
            entity_id,
        )
        return False

    async def _async_persistent(self, title: str, message: str) -> None:
        try:
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
        except HomeAssistantError as err:
            _LOGGER.warning("Persistent obavijest nije uspjela: %s", err)
