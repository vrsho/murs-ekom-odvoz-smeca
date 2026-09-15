"""Gumb za ručno osvježavanje kalendara."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
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
    async_add_entities([RefreshCalendarButton(coordinator)])


class RefreshCalendarButton(CoordinatorEntity[MursEkomCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:cloud-download"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: MursEkomCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_refresh"
        self._attr_device_info = _device(coordinator)

    @property
    def name(self) -> str:
        return self.coordinator.text("refresh")

    async def async_press(self) -> None:
        await self.coordinator.async_refresh_remote()
