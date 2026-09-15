"""Config flow za MURS-EKOM odvoz smeća."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TimeSelector,
)

from .const import (
    CONF_LOCATION,
    CONF_NOTIFY_DAYS_BEFORE,
    CONF_NOTIFY_ENABLED,
    CONF_NOTIFY_ENTITIES,
    CONF_NOTIFY_TIME,
    CONF_PULL_INTERVAL_DAYS,
    CONF_REFRESH_NOW,
    DEFAULT_NOTIFY_DAYS_BEFORE,
    DEFAULT_NOTIFY_ENABLED,
    DEFAULT_NOTIFY_TIME,
    DEFAULT_PULL_INTERVAL_DAYS,
    DOMAIN,
)
from .source import API_URL, USER_AGENT, fallback_locations, parse_locations

_LOGGER = logging.getLogger(__name__)


def _location_selector(locations: list[dict[str, str]]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                {"value": item["id"], "label": item["name"]} for item in locations
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _options_schema(
    defaults: dict[str, Any], locations: list[dict[str, str]]
) -> vol.Schema:
    location_default = defaults.get(CONF_LOCATION)
    if location_default is None and locations:
        location_default = locations[0]["id"]
    schema: dict[Any, Any] = {}
    if locations:
        schema[
            vol.Required(CONF_LOCATION, default=location_default)
        ] = _location_selector(locations)
    schema.update(
        {
            vol.Required(
                CONF_PULL_INTERVAL_DAYS,
                default=defaults.get(
                    CONF_PULL_INTERVAL_DAYS, DEFAULT_PULL_INTERVAL_DAYS
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=30,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_REFRESH_NOW,
                default=False,
            ): BooleanSelector(),
            vol.Required(
                CONF_NOTIFY_ENABLED,
                default=defaults.get(CONF_NOTIFY_ENABLED, DEFAULT_NOTIFY_ENABLED),
            ): BooleanSelector(),
            vol.Required(
                CONF_NOTIFY_DAYS_BEFORE,
                default=defaults.get(
                    CONF_NOTIFY_DAYS_BEFORE, DEFAULT_NOTIFY_DAYS_BEFORE
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=7,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_NOTIFY_TIME,
                default=defaults.get(CONF_NOTIFY_TIME, DEFAULT_NOTIFY_TIME),
            ): TimeSelector(),
            vol.Optional(
                CONF_NOTIFY_ENTITIES,
                default=defaults.get(CONF_NOTIFY_ENTITIES, []),
            ): EntitySelector(
                EntitySelectorConfig(domain="notify", multiple=True)
            ),
        }
    )
    return vol.Schema(schema)


async def async_load_locations(hass) -> list[dict[str, str]]:
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"{API_URL}?per_page=100&_fields=id,slug,link,title",
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        ) as response:
            response.raise_for_status()
            payload = await response.json()
        locations = parse_locations(payload)
        if locations:
            return locations
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Popis naselja nije dostupan: %s", err)
    return fallback_locations()


class MursEkomConfigFlow(ConfigFlow, domain=DOMAIN):
    """Postavljanje integracije iz UI-ja."""

    VERSION = 2

    def __init__(self) -> None:
        self._locations: list[dict[str, str]] = []

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MursEkomOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        self._locations = await async_load_locations(self.hass)
        if not self._locations:
            return self.async_abort(reason="no_locations")
        return await self.async_step_settings()

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            location = user_input[CONF_LOCATION]
            title = next(
                (item["name"] for item in self._locations if item["id"] == location),
                location,
            )
            return self.async_create_entry(
                title=title,
                data={CONF_LOCATION: location},
                options={
                    CONF_LOCATION: location,
                    CONF_PULL_INTERVAL_DAYS: int(
                        user_input[CONF_PULL_INTERVAL_DAYS]
                    ),
                    CONF_NOTIFY_ENABLED: bool(user_input[CONF_NOTIFY_ENABLED]),
                    CONF_NOTIFY_DAYS_BEFORE: int(
                        user_input[CONF_NOTIFY_DAYS_BEFORE]
                    ),
                    CONF_NOTIFY_TIME: user_input[CONF_NOTIFY_TIME],
                    CONF_NOTIFY_ENTITIES: user_input.get(CONF_NOTIFY_ENTITIES, []),
                },
            )

        return self.async_show_form(
            step_id="settings",
            data_schema=_options_schema({}, self._locations),
        )


class MursEkomOptionsFlow(OptionsFlow):
    """Naselje, tjedni pull i obavijesti."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        locations = await async_load_locations(self.hass)
        current = dict(self.config_entry.options)
        if CONF_LOCATION not in current:
            current[CONF_LOCATION] = self.config_entry.data.get(CONF_LOCATION)

        if user_input is not None:
            refresh_now = bool(user_input.pop(CONF_REFRESH_NOW, False))
            location = user_input[CONF_LOCATION]
            title = next(
                (item["name"] for item in locations if item["id"] == location),
                location,
            )
            self.hass.config_entries.async_update_entry(
                self.config_entry, title=title
            )
            options = {
                CONF_LOCATION: location,
                CONF_PULL_INTERVAL_DAYS: int(user_input[CONF_PULL_INTERVAL_DAYS]),
                CONF_NOTIFY_ENABLED: bool(user_input[CONF_NOTIFY_ENABLED]),
                CONF_NOTIFY_DAYS_BEFORE: int(user_input[CONF_NOTIFY_DAYS_BEFORE]),
                CONF_NOTIFY_TIME: user_input[CONF_NOTIFY_TIME],
                CONF_NOTIFY_ENTITIES: user_input.get(CONF_NOTIFY_ENTITIES, []),
            }
            if refresh_now:
                options["force_fetch_at"] = dt_util.now().isoformat()
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(current, locations),
        )
