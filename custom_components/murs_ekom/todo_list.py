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
    entity_id = find_todo_entity(hass)
    if entity_id is None and next(_managed_entries(hass), None) is None:
        await _async_create_list(hass, wanted)
        for _ in range(16):
            entity_id = find_todo_entity(hass)
            if entity_id:
                break
            await asyncio.sleep(0.25)
    if entity_id:
        _async_rename_entity(hass, entity_id, wanted)
        return entity_id
    _LOGGER.warning("Lista %s je uključena, ali entitet još nije dostupan", wanted)
    return None


def _async_rename_entity(hass: HomeAssistant, entity_id: str, wanted: str) -> None:
    registry = er.async_get(hass)
    item = registry.async_get(entity_id)
    if item is None or item.name == wanted:
        return
    try:
        registry.async_update_entity(entity_id, name=wanted)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Ime To-do liste nije ažurirano: %s", err)


async def _async_create_list(hass: HomeAssistant, wanted: str) -> None:
    try:
        await asyncio.wait_for(
            hass.config_entries.flow.async_init(
                _LOCAL_TODO,
                context={"source": "user"},
                data={_LIST_NAME_KEY: wanted},
            ),
            timeout=15,
        )
    except TimeoutError:
        _LOGGER.warning("Lista %s nije stvorena: timeout", wanted)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Lista %s nije stvorena: %s", wanted, err)


async def async_add_collection_item(
    hass: HomeAssistant,
    *,
    language: str,
    summary: str,
    due_date: str,
    description: str,
) -> bool:
    payloads = (
        {"item": summary, "due_date": due_date, "description": description},
        {"item": summary, "due_date": due_date},
        {"item": summary},
    )
    entity_id = await async_ensure_todo_list(hass, language)
    if entity_id is None or not hass.services.has_service("todo", "add_item"):
        _LOGGER.warning("Stavka na To-do listu nije dodana: %s", summary)
        return False
    if await _already_exists(hass, entity_id, summary, due_date):
        return True
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
            {"entity_id": entity_id, **payload},
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


async def async_collection_completed(
    hass: HomeAssistant, *, summary: str, due_date: str
) -> bool:
    entity_id = find_todo_entity(hass)
    if entity_id is None:
        return False
    items = await _list_items(hass, entity_id)
    for item in items:
        if not _matches_collection(item, summary, due_date):
            continue
        if str(item.get("status") or "").lower() == "completed":
            return True
    return False


def _matches_collection(item: dict, summary: str, due_date: str) -> bool:
    text = str(item.get("summary") or "")
    if text != summary and not text.endswith(summary):
        return False
    due = str(item.get("due") or item.get("due_date") or "")
    return not due or due.startswith(due_date)


async def _list_items(hass: HomeAssistant, entity_id: str) -> list[dict]:
    if not hass.services.has_service("todo", "get_items"):
        return []
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
