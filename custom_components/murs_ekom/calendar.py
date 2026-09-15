"""Kalendar odvoza za Home Assistant."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import MursEkomCoordinator
from .schedule import Collection
from .sensor import _device


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MursEkomCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MursEkomCalendar(coordinator)])


def _event_for(item: Collection, location: str) -> CalendarEvent:
    note = "Spremnik iznesite do 6:00 ujutro."
    if "bulky" in item.types:
        note += " Glomazni otpad prijavite na 040/543-314 najkasnije 2 dana prije."
    return CalendarEvent(
        start=item.date,
        end=item.date + timedelta(days=1),
        summary=item.label,
        description=note,
        location=location,
    )


class MursEkomCalendar(CoordinatorEntity[MursEkomCoordinator], CalendarEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "calendar"
    _attr_icon = "mdi:trash-can"
    _attr_attribution = ATTRIBUTION
    _attr_initial_color = "#2E7D32"

    def __init__(self, coordinator: MursEkomCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_calendar"
        self._attr_device_info = _device(coordinator)

    @property
    def event(self) -> CalendarEvent | None:
        item = self.coordinator.data.get("next") or self.coordinator.data.get(
            "today_item"
        )
        if item is None:
            return None
        return _event_for(item, self.coordinator.location_title)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        start = start_date.date()
        end = end_date.date()
        location = self.coordinator.location_title
        events: list[CalendarEvent] = []
        for item in self.coordinator.data.get("all", []):
            if item.date < start or item.date >= end:
                continue
            events.append(_event_for(item, location))
        return events
