"""Raspored odvoza bez ovisnosti o Home Assistantu."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable

from .schedule_data import LOCATIONS, RECYCLE_YARD, WASTE_TYPES

TYPE_ORDER = (
    "mixed",
    "bio",
    "plastic_paper",
    "metal_glass",
    "bulky",
    "branches",
    "christmas_trees",
)


@dataclass(frozen=True)
class Collection:
    date: date
    types: tuple[str, ...]

    @property
    def labels(self) -> list[str]:
        return [WASTE_TYPES[t]["name"] for t in self.types if t in WASTE_TYPES]

    @property
    def label(self) -> str:
        return ", ".join(self.labels)

    @property
    def icons(self) -> list[str]:
        return [WASTE_TYPES[t]["icon"] for t in self.types if t in WASTE_TYPES]

    @property
    def icon(self) -> str:
        if len(self.types) == 1 and self.types[0] in WASTE_TYPES:
            return WASTE_TYPES[self.types[0]]["icon"]
        return "mdi:trash-can"

    def includes(self, waste_type: str) -> bool:
        return waste_type in self.types


def location_choices() -> dict[str, str]:
    return {key: value["name"] for key, value in LOCATIONS.items()}


def location_name(location_id: str) -> str:
    return LOCATIONS[location_id]["name"]


def location_source(location_id: str) -> str:
    return LOCATIONS[location_id]["source"]


def _sorted_types(types: Iterable[str]) -> tuple[str, ...]:
    known = [t for t in TYPE_ORDER if t in types]
    extra = [t for t in types if t not in TYPE_ORDER]
    return tuple(known + extra)


def collections_from_events(events: Iterable) -> list[Collection]:
    items: list[Collection] = []
    for event in events:
        if isinstance(event, dict):
            raw_date = event["date"]
            types = event["types"]
        else:
            raw_date, types = event
        items.append(
            Collection(
                date=date.fromisoformat(raw_date),
                types=_sorted_types(types),
            )
        )
    items.sort(key=lambda item: item.date)
    return items


def collections_for(location_id: str) -> list[Collection]:
    location = LOCATIONS[location_id]
    return collections_from_events(location["events"])


def upcoming(
    location_id: str,
    today: date,
    *,
    waste_type: str | None = None,
) -> list[Collection]:
    return upcoming_from(collections_for(location_id), today, waste_type=waste_type)


def upcoming_from(
    items: list[Collection],
    today: date,
    *,
    waste_type: str | None = None,
) -> list[Collection]:
    result = [item for item in items if item.date >= today]
    if waste_type:
        result = [item for item in result if item.includes(waste_type)]
    return result


def next_collection(
    location_id: str,
    today: date,
    *,
    waste_type: str | None = None,
) -> Collection | None:
    items = upcoming(location_id, today, waste_type=waste_type)
    return items[0] if items else None


def next_from(
    items: list[Collection],
    today: date,
    *,
    waste_type: str | None = None,
) -> Collection | None:
    matches = upcoming_from(items, today, waste_type=waste_type)
    return matches[0] if matches else None


def collection_on(location_id: str, day: date) -> Collection | None:
    return collection_on_from(collections_for(location_id), day)


def collection_on_from(items: list[Collection], day: date) -> Collection | None:
    for item in items:
        if item.date == day:
            return item
        if item.date > day:
            break
    return None


def days_until(item: Collection | None, today: date) -> int | None:
    if item is None:
        return None
    return (item.date - today).days


def when_label(item: Collection | None, today: date) -> str:
    delta = days_until(item, today)
    if delta is None:
        return "Nema termina"
    if delta == 0:
        return "Danas"
    if delta == 1:
        return "Sutra"
    return f"Za {delta} dana"


def format_date_hr(value: date) -> str:
    return f"{value.day:02d}.{value.month:02d}.{value.year}."


def notify_target_date(today: date, days_before: int) -> date:
    return today + timedelta(days=days_before)


def parse_time(value: str | time) -> tuple[int, int, int]:
    if isinstance(value, time):
        return value.hour, value.minute, value.second
    text = str(value)
    parsed = datetime.strptime(text, "%H:%M:%S" if text.count(":") == 2 else "%H:%M")
    return parsed.hour, parsed.minute, parsed.second


def waste_type_name(waste_type: str) -> str:
    return WASTE_TYPES[waste_type]["name"]


def waste_type_icon(waste_type: str) -> str:
    return WASTE_TYPES[waste_type]["icon"]


def recycle_yard_info() -> dict:
    return RECYCLE_YARD
