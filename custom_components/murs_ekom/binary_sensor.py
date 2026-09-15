"""Binarni senzor je li danas dan odvoza."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import MursEkomCoordinator
from .sensor import _device


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MursEkomCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CollectionTodaySensor(coordinator)])


class CollectionTodaySensor(CoordinatorEntity[MursEkomCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:trash-can"
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: MursEkomCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_today"
        self._attr_device_info = _device(coordinator)

    @property
    def name(self) -> str:
        return self.coordinator.text("collection_today")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("today_item") is not None

    @property
    def extra_state_attributes(self) -> dict:
        item = self.coordinator.data.get("today_item")
        if item is None:
            return {"types_label": []}
        return {
            "types": list(item.types),
            "types_label": self.coordinator.types_label(item.types),
            "prepare_by": "06:00",
        }
