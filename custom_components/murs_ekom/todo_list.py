"""To-do lista za podsjetnike odvoza."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .i18n import text as i18n_text

_LOGGER = logging.getLogger(__name__)

_LOCAL_TODO = "local_todo"
_LIST_NAME_KEY = "todo_list_name"
_STORAGE_KEY = "storage_key"
_MANAGED_NAMES = frozenset({"smeće", "smece", "waste"})
_MANAGED_ENTITY_IDS = frozenset({"todo.smece", "todo.smeće", "todo.waste"})


def list_name_for(language: str) -> str:
    return i18n_text(language, "todo_list_name")


def _folded(value: str) -> str:
    return value.strip().casefold()


def _is_managed_name(name: str) -> bool:
    return _folded(name) in _MANAGED_NAMES


def _managed_entries(hass: HomeAssistant):
    for entry in hass.config_entries.async_entries(_LOCAL_TODO):
        name = str(entry.data.get(_LIST_NAME_KEY) or entry.title or "")
        key = str(entry.data.get(_STORAGE_KEY) or "")
        if _is_managed_name(name) or key in _MANAGED_NAMES:
            yield entry


def _entity_for_entry(hass: HomeAssistant, entry) -> str | None:
    registry = er.async_get(hass)
    for item in er.async_entries_for_config_entry(registry, entry.entry_id):
        if item.domain == "todo" and not item.disabled:
            return item.entity_id
    key = str(entry.data.get(_STORAGE_KEY) or "")
    if key and hass.states.get(f"todo.{key}"):
        return f"todo.{key}"
    return None


def find_todo_entity(hass: HomeAssistant) -> str | None:
    for state in hass.states.async_all("todo"):
        if state.entity_id in _MANAGED_ENTITY_IDS or _is_managed_name(state.name or ""):
            return state.entity_id
    for entry in _managed_entries(hass):
        entity_id = _entity_for_entry(hass, entry)
        if entity_id:
            return entity_id
    return None


async def async_ensure_todo_list(hass: HomeAssistant, language: str) -> str | None:
    wanted = list_name_for(language)
    existing = next(_managed_entries(hass), None)
    if existing is None:
        await _async_create_list(hass, wanted)
    else:
        await _async_maybe_rename(hass, existing, wanted)
    await _async_wait_ready(hass)
    entity_id = find_todo_entity(hass)
    if entity_id is None:
        _LOGGER.warning("Lista %s je uključena, ali entitet još nije dostupan", wanted)
    return entity_id


async def _async_maybe_rename(hass: HomeAssistant, entry, wanted: str) -> None:
    current = str(entry.data.get(_LIST_NAME_KEY) or entry.title or "")
    if current == wanted:
        return
    hass.config_entries.async_update_entry(
        entry,
        title=wanted,
        data={**entry.data, _LIST_NAME_KEY: wanted},
    )
    try:
        await hass.config_entries.async_reload(entry.entry_id)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Reload liste %s: %s", wanted, err)


async def _async_create_list(hass: HomeAssistant, wanted: str) -> None:
    try:
        await hass.config_entries.flow.async_init(
            _LOCAL_TODO,
            context={"source": "user"},
            data={_LIST_NAME_KEY: wanted},
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Lista %s nije stvorena: %s", wanted, err)


async def _async_wait_ready(hass: HomeAssistant) -> None:
    for _ in range(20):
        if hass.services.has_service("todo", "add_item") and find_todo_entity(hass):
            return
        await asyncio.sleep(0.25)


async def async_add_collection_item(
    hass: HomeAssistant,
    *,
    language: str,
    summary: str,
    due_date: str,
    description: str,
) -> bool:
    entity_id = None
    payloads = (
        {"item": summary, "due_date": due_date, "description": description},
        {"item": summary, "due_date": due_date},
        {"item": summary},
    )
    for attempt in range(6):
        entity_id = await async_ensure_todo_list(hass, language)
        if entity_id is None or not hass.services.has_service("todo", "add_item"):
            await asyncio.sleep(0.5)
            continue
        if await _already_exists(hass, entity_id, summary, due_date):
            return True
        payload = payloads[min(attempt, len(payloads) - 1)]
        if await _async_call_add(hass, entity_id, payload):
            _LOGGER.info("Dodana stavka na %s: %s", entity_id, summary)
            return True
        await asyncio.sleep(0.5)
    _LOGGER.warning("Stavka na To-do listu nije dodana: %s", summary)
    return False


async def _async_call_add(hass: HomeAssistant, entity_id: str, payload: dict) -> bool:
    data = {"entity_id": entity_id, **payload}
    try:
        await hass.services.async_call(
            "todo",
            "add_item",
            data,
            blocking=True,
            target={"entity_id": entity_id},
        )
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("todo.add_item nije uspio na %s: %s", entity_id, err)
        try:
            await hass.services.async_call(
                "todo",
                "add_item",
                payload,
                blocking=True,
                target={"entity_id": entity_id},
            )
            return True
        except Exception as inner:  # noqa: BLE001
            _LOGGER.warning("todo.add_item nije uspio: %s", inner)
            return False


async def _already_exists(
    hass: HomeAssistant, entity_id: str, summary: str, due_date: str
) -> bool:
    if not hass.services.has_service("todo", "get_items"):
        return False
    try:
        response = await hass.services.async_call(
            "todo",
            "get_items",
            {"entity_id": entity_id},
            blocking=True,
            return_response=True,
            target={"entity_id": entity_id},
        )
    except HomeAssistantError:
        return False
    if not isinstance(response, dict):
        return False
    items = (response.get(entity_id) or {}).get("items") or []
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("summary") or "") != summary:
            continue
        due = str(item.get("due") or item.get("due_date") or "")
        if not due or due.startswith(due_date):
            return True
    return False
