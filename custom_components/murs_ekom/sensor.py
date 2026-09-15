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
from .i18n import format_date, when_text
from .schedule import TYPE_ORDER, WASTE_TYPES, days_until


def _device(coordinator: MursEkomCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.entry.entry_id)},
        name=f"{coordinator.text('device_name')} ({coordinator.location_title})",
        manufacturer="MURS-EKOM d.o.o.",
        model=coordinator.text("calendar"),
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
    _attr_icon = "mdi:trash-can"
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: MursEkomCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_next"
        self._attr_device_info = _device(coordinator)

    @property
    def name(self) -> str:
        return self.coordinator.text("next_collection")

    @property
    def native_value(self) -> str:
        data = self.coordinator.data or {}
        item = data.get("next")
        if item is None:
            return self.coordinator.text("no_upcoming")
        return self.coordinator.types_label(item.types)

    @property
    def icon(self) -> str:
        item = self.coordinator.data.get("next")
        return item.icon if item else "mdi:trash-can"

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        item = data.get("next")
        today = data["today"]
        lang = self.coordinator.language
        if item is None:
            return {
                "days_until": None,
                "when": when_text(lang, None),
                "location": self.coordinator.location_title,
                "last_pull": data.get("last_pull"),
            }
        days = days_until(item, today)
        return {
            "date": item.date.isoformat(),
            "date_label": format_date(item.date),
            "days_until": days,
            "when": when_text(lang, days),
            "types": list(item.types),
            "types_label": self.coordinator.types_label(item.types),
            "location": self.coordinator.location_title,
            "prepare_by": "06:00",
            "last_pull": data.get("last_pull"),
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
            icon=info["icon"],
        )
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{waste_type}"
        self._attr_device_info = _device(coordinator)
        self._attr_icon = info["icon"]

    @property
    def name(self) -> str:
        return self.coordinator.waste_label(self._waste_type)

    @property
    def native_value(self) -> str:
        data = self.coordinator.data or {}
        item = (data.get("per_type") or {}).get(self._waste_type)
        last = (data.get("last_type") or {}).get(self._waste_type)
        today = data.get("today")
        days = days_until(item, today) if today is not None else None
        last_date = last.date if last is not None else None
        return when_text(self.coordinator.language, days, last_date)

    @property
    def extra_state_attributes(self) -> dict:
        item = self.coordinator.data["per_type"].get(self._waste_type)
        last = self.coordinator.data.get("last_type", {}).get(self._waste_type)
        today = self.coordinator.data["today"]
        attrs: dict = {"days_until": days_until(item, today)}
        if item is not None:
            attrs.update(
                {
                    "date": item.date.isoformat(),
                    "date_label": format_date(item.date),
                    "also_collected": [
                        self.coordinator.waste_label(t)
                        for t in item.types
                        if t != self._waste_type
                    ],
                }
            )
        if last is not None:
            attrs["last_date"] = last.date.isoformat()
            attrs["last_date_label"] = format_date(last.date)
        return attrs
