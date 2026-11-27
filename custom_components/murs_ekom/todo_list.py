"""To-do lista za podsjetnike odvoza."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


async def async_add_collection_item(
    hass: HomeAssistant,
    entity_id: str,
    *,
    summary: str,
    due_date: str,
    description: str,
    due_datetime: str | None = None,
) -> bool:
    if hass.states.get(entity_id) is None or not hass.services.has_service(
        "todo", "add_item"
    ):
        _LOGGER.warning("To-do lista %s nije dostupna", entity_id)
        return False
    if await _already_exists(hass, entity_id, summary, due_date):
        if due_datetime:
            await _async_call_update(
                hass,
                entity_id,
                summary,
                due_datetime=due_datetime,
                description=description,
            )
        return True
    payloads: tuple[dict, ...] = ()
    if due_datetime:
        payloads = (
            {
                "item": summary,
                "due_datetime": due_datetime,
                "description": description,
            },
            {"item": summary, "due_datetime": due_datetime},
        )
    payloads = payloads + (
        {"item": summary, "due_date": due_date, "description": description},
        {"item": summary, "due_date": due_date},
        {"item": summary, "description": description},
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
        _LOGGER.debug("todo.add_item na %s nije uspio: %s", entity_id, err)
        return False


async def _async_call_update(
    hass: HomeAssistant,
    entity_id: str,
    summary: str,
    *,
    due_datetime: str,
    description: str,
) -> bool:
    if not hass.services.has_service("todo", "update_item"):
        return False
    try:
        await hass.services.async_call(
            "todo",
            "update_item",
            {
                "item": summary,
                "due_datetime": due_datetime,
                "description": description,
            },
            blocking=True,
            target={"entity_id": entity_id},
        )
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("todo.update_item na %s: %s", entity_id, err)
        return False


async def async_collection_completed(
    hass: HomeAssistant, entity_id: str, *, summary: str, due_date: str
) -> bool:
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
    if hass.states.get(entity_id) is None or not hass.services.has_service(
        "todo", "get_items"
    ):
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
