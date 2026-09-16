"""Prijevodi UI teksta i vrsta otpada."""

from __future__ import annotations

from datetime import date

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_LANGUAGE, DEFAULT_LANGUAGE, LANG_EN, LANG_HR, LANG_SYSTEM

WASTE_NAMES: dict[str, dict[str, str]] = {
    LANG_HR: {
        "mixed": "Miješani komunalni otpad",
        "bio": "Bio otpad",
        "plastic_paper": "Plastika i papir",
        "plastic": "Plastika",
        "paper": "Papir",
        "metal_glass": "Metal, Tetrapak, Staklena ambalaža",
        "bulky": "Glomazni otpad",
        "branches": "Granje",
        "christmas_trees": "Božićna drvca",
    },
    LANG_EN: {
        "mixed": "Mixed municipal waste",
        "bio": "Bio waste",
        "plastic_paper": "Plastic and paper",
        "plastic": "Plastic",
        "paper": "Paper",
        "metal_glass": "Metal, Tetrapak and glass",
        "bulky": "Bulky waste",
        "branches": "Branches",
        "christmas_trees": "Christmas trees",
    },
}

TEXT: dict[str, dict[str, str]] = {
    LANG_HR: {
        "device_name": "Odvoz smeća",
        "next_collection": "Sljedeći odvoz",
        "collection_today": "Odvoz danas",
        "calendar": "Kalendar odvoza",
        "refresh": "Osvježi kalendar",
        "today": "Danas",
        "tomorrow": "Sutra",
        "in_days": "Za {n} dana",
        "no_upcoming": "Nema sljedećeg termina",
        "no_upcoming_last": "Nema sljedećeg (zadnji {date})",
        "prepare": "Spremnik iznesite do 6:00 ujutro.",
        "bulky_note": "Glomazni otpad prijavite na 040/543-314 najkasnije 2 dana prije.",
        "branches_note": "Granje ostavite ispred kuće na dan odvoza.",
        "notify_title": "Odvoz smeća {when}",
        "notify_body": "{when} ({date}) odvoze: {types}.",
        "notify_test": "TEST",
        "notify_empty": "Testna obavijest. Trenutačno nema predstojećeg termina.",
        "todo_list_name": "Smeće",
        "remind_title": "Odvoz smeća danas",
        "remind_body": "To-Do stavka još nije označena kao riješena. Danas ({date}) odvoze: {types}.",
    },
    LANG_EN: {
        "device_name": "Waste collection",
        "next_collection": "Next collection",
        "collection_today": "Collection today",
        "calendar": "Collection calendar",
        "refresh": "Refresh calendar",
        "today": "Today",
        "tomorrow": "Tomorrow",
        "in_days": "In {n} days",
        "no_upcoming": "No upcoming collection",
        "no_upcoming_last": "No upcoming (last {date})",
        "prepare": "Put bins out by 6:00 in the morning.",
        "bulky_note": "Book bulky waste on 040/543-314 at least 2 days in advance.",
        "branches_note": "Leave branches in front of the house on collection day.",
        "notify_title": "Waste collection {when}",
        "notify_body": "{when} ({date}): {types}.",
        "notify_test": "TEST",
        "notify_empty": "Test notification. There is no upcoming collection.",
        "todo_list_name": "Waste",
        "remind_title": "Waste collection today",
        "remind_body": "The To-Do item is not marked done. Today ({date}): {types}.",
    },
}


def resolve_language(hass: HomeAssistant | None, entry: ConfigEntry | None) -> str:
    raw = DEFAULT_LANGUAGE
    if entry is not None:
        raw = str(entry.options.get(CONF_LANGUAGE, DEFAULT_LANGUAGE))
    if raw == LANG_HR:
        return LANG_HR
    if raw == LANG_EN:
        return LANG_EN
    ha_lang = "en"
    if hass is not None:
        ha_lang = str(getattr(hass.config, "language", None) or "en").lower()
    if ha_lang.startswith("hr"):
        return LANG_HR
    return LANG_EN


def text(lang: str, key: str, **kwargs) -> str:
    table = TEXT.get(lang) or TEXT[LANG_EN]
    value = table.get(key) or TEXT[LANG_EN].get(key, key)
    return value.format(**kwargs) if kwargs else value


def waste_name(lang: str, waste_type: str) -> str:
    names = WASTE_NAMES.get(lang) or WASTE_NAMES[LANG_EN]
    return names.get(waste_type) or WASTE_NAMES[LANG_HR].get(waste_type, waste_type)


def waste_names(lang: str, types: list[str] | tuple[str, ...]) -> list[str]:
    return [waste_name(lang, item) for item in types]


def collection_label(lang: str, types: list[str] | tuple[str, ...]) -> str:
    return ", ".join(waste_names(lang, types))


def when_text(lang: str, days: int | None, last_date: date | None = None) -> str:
    if days is None:
        if last_date is not None:
            return text(lang, "no_upcoming_last", date=format_date(last_date))
        return text(lang, "no_upcoming")
    if days == 0:
        return text(lang, "today")
    if days == 1:
        return text(lang, "tomorrow")
    return text(lang, "in_days", n=days)


def format_date(value: date) -> str:
    return f"{value.day:02d}.{value.month:02d}.{value.year}."
