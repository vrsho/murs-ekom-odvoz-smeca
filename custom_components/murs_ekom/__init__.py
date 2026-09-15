"""MURS-EKOM odvoz smeća za Home Assistant."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.event import async_track_time_change

from .const import CONF_LOCATION, CONF_PULL_INTERVAL_DAYS, DEFAULT_PULL_INTERVAL_DAYS, DOMAIN
from .coordinator import MursEkomCoordinator
from .notifier import MursEkomNotifier

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = MursEkomCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    notifier = MursEkomNotifier(hass, entry, coordinator)
    await notifier.async_start()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.data[DOMAIN][f"{entry.entry_id}_notifier"] = notifier

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    @callback
    def _midnight(_now) -> None:
        hass.async_create_task(coordinator.async_request_refresh())

    entry.async_on_unload(
        async_track_time_change(hass, _midnight, hour=0, minute=0, second=10)
    )
    _async_register_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.version < 2:
        options = dict(entry.options)
        options.setdefault(CONF_LOCATION, entry.data.get(CONF_LOCATION))
        options.setdefault(CONF_PULL_INTERVAL_DAYS, DEFAULT_PULL_INTERVAL_DAYS)
        hass.config_entries.async_update_entry(entry, options=options, version=2)
        _LOGGER.info("Migracija unosa MURS-EKOM na verziju 2")
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    notifier: MursEkomNotifier | None = hass.data[DOMAIN].pop(
        f"{entry.entry_id}_notifier", None
    )
    if notifier:
        await notifier.async_stop()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


def _coordinators(hass: HomeAssistant) -> list[MursEkomCoordinator]:
    return [
        value
        for value in hass.data.get(DOMAIN, {}).values()
        if isinstance(value, MursEkomCoordinator)
    ]


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.data[DOMAIN].get("services_registered"):
        return

    async def _test_notification(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        if entry_id:
            notifiers = [hass.data[DOMAIN].get(f"{entry_id}_notifier")]
        else:
            notifiers = [
                value
                for key, value in hass.data[DOMAIN].items()
                if isinstance(key, str) and key.endswith("_notifier")
            ]
        notifiers = [item for item in notifiers if item is not None]
        if not notifiers:
            _LOGGER.warning("Nema aktivne MURS-EKOM integracije za test obavijesti")
            return
        for notifier in notifiers:
            await notifier.async_send_test()

    async def _refresh(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        coordinators = _coordinators(hass)
        if entry_id:
            coordinators = [
                item for item in coordinators if item.entry.entry_id == entry_id
            ]
        if not coordinators:
            _LOGGER.warning("Nema aktivne MURS-EKOM integracije za osvježavanje")
            return
        for coordinator in coordinators:
            await coordinator.async_refresh_remote()

    schema = vol.Schema({vol.Optional("entry_id"): str})
    hass.services.async_register(
        DOMAIN, "test_obavijest", _test_notification, schema=schema
    )
    hass.services.async_register(DOMAIN, "osvjezi", _refresh, schema=schema)
    hass.data[DOMAIN]["services_registered"] = True
