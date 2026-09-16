"""To-do lista Smeće za podsjetnike odvoza."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import TODO_LIST_NAME

_LOGGER = logging.getLogger(__name__)

_LOCAL_TODO = "local_todo"
_LIST_NAME_KEY = "todo_list_name"


def find_smece_entity(hass: HomeAssistant) -> str | None:
    wanted = TODO_LIST_NAME.casefold()
    for state in hass.states.async_all("todo"):
        name = (state.name or "").strip().casefold()
        if name == wanted or state.entity_id in ("todo.smece", "todo.smeće"):
            return state.entity_id
    for entry in hass.config_entries.async_entries(_LOCAL_TODO):
        name = str(entry.data.get(_LIST_NAME_KEY) or entry.title or "")
        if name.casefold() != wanted:
            continue
        key = str(entry.data.get("storage_key") or "")
        if key and hass.states.get(f"todo.{key}"):
            return f"todo.{key}"
    return None


def _has_smece_entry(hass: HomeAssistant) -> bool:
    wanted = TODO_LIST_NAME.casefold()
    return any(
        str(entry.data.get(_LIST_NAME_KEY) or entry.title or "").casefold() == wanted
        for entry in hass.config_entries.async_entries(_LOCAL_TODO)
    )


async def async_ensure_smece_list(hass: HomeAssistant) -> str | None:
    existing = find_smece_entity(hass)
    if existing:
        return existing

    if not _has_smece_entry(hass):
        try:
            result = await hass.config_entries.flow.async_init(
                _LOCAL_TODO,
                context={"source": "user"},
                data={_LIST_NAME_KEY: TODO_LIST_NAME},
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Lista %s nije stvorena: %s", TODO_LIST_NAME, err)
            return find_smece_entity(hass)

        if getattr(result, "type", None) == "abort" or (
            isinstance(result, dict) and result.get("type") == "abort"
        ):
            _LOGGER.debug("Lista %s već postoji ili flow je prekinut", TODO_LIST_NAME)

    for _ in range(20):
        entity_id = find_smece_entity(hass)
        if entity_id:
            return entity_id
        await asyncio.sleep(0.25)
    _LOGGER.warning("Lista %s je uključena, ali entitet još nije dostupan", TODO_LIST_NAME)
    return None


async def async_add_collection_item(
    hass: HomeAssistant,
    *,
    summary: str,
    due_date: str,
    description: str,
) -> bool:
    entity_id = await async_ensure_smece_list(hass)
    if entity_id is None:
        return False
    if await _already_exists(hass, entity_id, summary, due_date):
        return True
    payload = {"item": summary, "due_date": due_date, "description": description}
    try:
        await hass.services.async_call(
            "todo",
            "add_item",
            payload,
            blocking=True,
            target={"entity_id": entity_id},
        )
        _LOGGER.info("Dodana stavka na %s: %s", entity_id, summary)
        return True
    except HomeAssistantError as err:
        _LOGGER.warning("Stavka na To-do listu nije dodana s rokom: %s", err)
    try:
        await hass.services.async_call(
            "todo",
            "add_item",
            {"item": summary, "description": description},
            blocking=True,
            target={"entity_id": entity_id},
        )
        _LOGGER.info("Dodana stavka na %s: %s", entity_id, summary)
        return True
    except HomeAssistantError as err:
        _LOGGER.warning("Stavka na To-do listu nije dodana: %s", err)
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
            {},
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
        if str(item.get("summary") or item.get("uid") or "") != summary:
            continue
        due = str(item.get("due") or item.get("due_date") or "")
        if due.startswith(due_date):
            return True
    return False
