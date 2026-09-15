"""Senzori sljedećeg odvoza."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import MursEkomCoordinator
from .schedule import TYPE_ORDER, WASTE_TYPES, days_until, format_date_hr, when_label


def _device(coordinator: MursEkomCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.entry.entry_id)},
        name=f"Odvoz smeća ({coordinator.location_title})",
        manufacturer="MURS-EKOM d.o.o.",
        model="Kalendar odvoza",
        configuration_url=coordinator.source_url,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MursEkomCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [NextCollectionSensor(coordinator)]
    entities.extend(
        WasteTypeSensor(coordinator, waste_type) for waste_type in TYPE_ORDER
    )
    async_add_entities(entities)


class NextCollectionSensor(CoordinatorEntity[MursEkomCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "next_collection"
    _attr_icon = "mdi:trash-can"
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: MursEkomCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_next"
        self._attr_device_info = _device(coordinator)

    @property
    def native_value(self) -> str | None:
        item = self.coordinator.data.get("next")
        if item is None:
            return None
        return item.label

    @property
    def icon(self) -> str:
        item = self.coordinator.data.get("next")
        return item.icon if item else "mdi:trash-can"

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        item = data.get("next")
        today = data["today"]
        if item is None:
            return {
                "days_until": None,
                "when": "Nema termina",
                "location": self.coordinator.location_title,
                "last_pull": data.get("last_pull"),
                "source": data.get("source"),
            }
        return {
            "date": item.date.isoformat(),
            "date_hr": format_date_hr(item.date),
            "days_until": days_until(item, today),
            "when": when_label(item, today),
            "types": list(item.types),
            "types_hr": item.labels,
            "location": self.coordinator.location_title,
            "prepare_by": "06:00",
            "last_pull": data.get("last_pull"),
            "source": data.get("source"),
            "pull_days": data.get("pull_days"),
        }


class WasteTypeSensor(CoordinatorEntity[MursEkomCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: MursEkomCoordinator, waste_type: str) -> None:
        super().__init__(coordinator)
        info = WASTE_TYPES[waste_type]
        self._waste_type = waste_type
        self.entity_description = SensorEntityDescription(
            key=waste_type,
            translation_key=waste_type,
            icon=info["icon"],
        )
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{waste_type}"
        self._attr_device_info = _device(coordinator)
        self._attr_icon = info["icon"]

    @property
    def native_value(self) -> str | None:
        item = self.coordinator.data["per_type"].get(self._waste_type)
        if item is None:
            return None
        today = self.coordinator.data["today"]
        return when_label(item, today)

    @property
    def extra_state_attributes(self) -> dict:
        item = self.coordinator.data["per_type"].get(self._waste_type)
        today = self.coordinator.data["today"]
        if item is None:
            return {"days_until": None}
        return {
            "date": item.date.isoformat(),
            "date_hr": format_date_hr(item.date),
            "days_until": days_until(item, today),
            "also_collected": [
                WASTE_TYPES[t]["name"] for t in item.types if t != self._waste_type
            ],
        }
