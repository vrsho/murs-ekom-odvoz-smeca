"""To-do lista za podsjetnike odvoza."""

from __future__ import annotations

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


def find_todo_entity(hass: HomeAssistant) -> str | None:
    for state in hass.states.async_all("todo"):
        if state.entity_id in _MANAGED_ENTITY_IDS or _is_managed_name(state.name or ""):
            return state.entity_id
    registry = er.async_get(hass)
    for entity_id in _MANAGED_ENTITY_IDS:
        item = registry.async_get(entity_id)
        if item is not None and not item.disabled:
            return item.entity_id
    for entry in hass.config_entries.async_entries(_LOCAL_TODO):
        name = str(entry.data.get(_LIST_NAME_KEY) or entry.title or "")
        key = str(entry.data.get(_STORAGE_KEY) or "")
        if not _is_managed_name(name) and key not in _MANAGED_NAMES:
            continue
        for item in er.async_entries_for_config_entry(registry, entry.entry_id):
            if item.domain == "todo" and not item.disabled:
                return item.entity_id
        if key:
            return f"todo.{key}"
    return None


async def async_ensure_todo_list(hass: HomeAssistant, language: str) -> str | None:
    entity_id = find_todo_entity(hass)
    if entity_id:
        return entity_id
    _LOGGER.warning(
        "Nema To-Do liste %s. Dodaj Local to-do listu s tim imenom, pa uključi opciju ponovno.",
        list_name_for(language),
    )
    return None


async def async_add_collection_item(
    hass: HomeAssistant,
    *,
    language: str,
    summary: str,
    due_date: str,
    description: str,
) -> bool:
    entity_id = await async_ensure_todo_list(hass, language)
    if entity_id is None or not hass.services.has_service("todo", "add_item"):
        _LOGGER.warning("Stavka na To-do listu nije dodana: %s", summary)
        return False
    if await _already_exists(hass, entity_id, summary, due_date):
        return True
    payloads = (
        {"item": summary, "due_date": due_date, "description": description},
        {"item": summary, "due_date": due_date},
        {"item": summary},
    )
    for payload in payloads:
        if await _async_call_add(hass, entity_id, payload):
            _LOGGER.info("Dodana stavka na %s: %s", entity_id, summary)
            return True
    _LOGGER.warning("Stavka na To-do listu nije dodana: %s", summary)
    return False


async def _async_call_add(hass: HomeAssistant, entity_id: str, payload: dict) -> bool:
    try:
        await hass.services.async_call(
            "todo",
            "add_item",
            payload,
            blocking=True,
            target={"entity_id": entity_id},
        )
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("todo.add_item na %s nije uspio: %s", entity_id, err)
        return False


async def async_collection_completed(
    hass: HomeAssistant, *, summary: str, due_date: str
) -> bool:
    entity_id = find_todo_entity(hass)
    if entity_id is None:
        return False
    for item in await _list_items(hass, entity_id):
        if not _matches_collection(item, summary, due_date):
            continue
        if str(item.get("status") or "").lower() == "completed":
            return True
    return False


def _matches_collection(item: dict, summary: str, due_date: str) -> bool:
    text = str(item.get("summary") or "")
    if text != summary:
        return False
    due = str(item.get("due") or item.get("due_date") or "")
    return bool(due) and due.startswith(due_date)


async def _list_items(hass: HomeAssistant, entity_id: str) -> list[dict]:
    if not hass.services.has_service("todo", "get_items"):
        return []
    try:
        response = await hass.services.async_call(
            "todo",
            "get_items",
            {},
            blocking=True,
            return_response=True,
            target={"entity_id": entity_id},
        )
    except HomeAssistantError:
        return []
    if not isinstance(response, dict):
        return []
    items = (response.get(entity_id) or {}).get("items") or []
    return [item for item in items if isinstance(item, dict)]


async def _already_exists(
    hass: HomeAssistant, entity_id: str, summary: str, due_date: str
) -> bool:
    for item in await _list_items(hass, entity_id):
        if _matches_collection(item, summary, due_date):
            return True
    return False
