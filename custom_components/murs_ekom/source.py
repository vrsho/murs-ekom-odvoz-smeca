"""Dohvat i parsiranje kalendara odvoza."""

from __future__ import annotations

from datetime import date, datetime
import html as html_lib
import re
from typing import Any
from urllib.parse import urljoin

ARCHIVE_URL = "https://muralist.hr/kalendar-odvoza/"
API_URL = "https://muralist.hr/wp-json/wp/v2/kalendar_odvoza"
USER_AGENT = "MURS-EKOM-HA/1.1 (Vrsho; info@vrsho.com)"

WASTE_LABELS: dict[str, str] = {
    "bio otpad": "bio",
    "biootpad": "bio",
    "miješani komunalni otpad": "mixed",
    "mijesani komunalni otpad": "mixed",
    "plastika": "plastic_paper",
    "papir": "plastic_paper",
    "plastika i papir": "plastic_paper",
    "plastika papir": "plastic_paper",
    "metal, tetrapak, staklena ambalaža": "metal_glass",
    "metal, tetrapak i staklo": "metal_glass",
    "metal tetrapak staklena ambalaza": "metal_glass",
}

SECTION_TYPES: list[tuple[str, str]] = [
    ("božićna drvca", "christmas_trees"),
    ("bozicna drvca", "christmas_trees"),
    ("glomazni otpad — granje", "branches"),
    ("glomazni otpad - granje", "branches"),
    ("granje", "branches"),
    ("glomazni komunalni otpad", "bulky"),
    ("glomazni otpad", "bulky"),
]

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_YEAR_RE = re.compile(
    r"<strong>Godina:</strong>\s*(\d{4})", re.IGNORECASE
)
_LOCATION_RE = re.compile(
    r"<strong>Lokacija:</strong>\s*(.*?)</p>", re.IGNORECASE | re.DOTALL
)
_SECTION_RE = re.compile(
    r'<div class="kalendar-section">\s*<h3>(.*?)</h3>\s*<ul class="date-list">(.*?)</ul>',
    re.IGNORECASE | re.DOTALL,
)
_ROW_RE = re.compile(
    r"<tr>\s*<td>(.*?)</td>\s*<td class=\"waste-types\">(.*?)</td>\s*</tr>",
    re.IGNORECASE | re.DOTALL,
)
_BADGE_RE = re.compile(
    r'<span class="waste-badge[^"]*"[^>]*>(.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)
_DATE_ITEM_RE = re.compile(r"<li>(.*?)</li>", re.IGNORECASE | re.DOTALL)
_DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(?:(\d{4}))?")


def _clean(text: str) -> str:
    text = html_lib.unescape(_TAG_RE.sub(" ", text or ""))
    return _SPACE_RE.sub(" ", text).strip()


def _norm(text: str) -> str:
    return (
        _clean(text)
        .lower()
        .replace("–", "-")
        .replace("—", "-")
        .replace("š", "s")
        .replace("ć", "c")
        .replace("č", "c")
        .replace("ž", "z")
        .replace("đ", "d")
    )


def _map_waste_label(label: str) -> str | None:
    key = _norm(label)
    for raw, mapped in WASTE_LABELS.items():
        needle = _norm(raw)
        if key == needle or needle in key:
            return mapped
    return None


def _map_section(title: str) -> str | None:
    key = _norm(title)
    for needle, mapped in SECTION_TYPES:
        if _norm(needle) in key:
            return mapped
    return None


def _parse_date(text: str, default_year: int) -> date | None:
    match = _DATE_RE.search(_clean(text))
    if not match:
        return None
    day, month, year = match.groups()
    try:
        return date(int(year or default_year), int(month), int(day))
    except ValueError:
        return None


def _display_name(title: str) -> str:
    name = _clean(title).replace("–", "-").replace("—", "-")
    name = re.sub(r"\s*-\s*\d{4}\s*$", "", name).strip()
    return name


def parse_locations(payload: list[dict[str, Any]]) -> list[dict[str, str]]:
    locations: list[dict[str, str]] = []
    for item in payload:
        slug = item.get("slug") or ""
        link = item.get("link") or urljoin(ARCHIVE_URL, slug)
        title = _display_name((item.get("title") or {}).get("rendered") or slug)
        if not slug:
            continue
        locations.append({"id": slug, "name": title, "url": link})
    locations.sort(key=lambda loc: loc["name"].lower())
    return locations


def parse_calendar_html(html: str, *, url: str = "", slug: str = "") -> dict[str, Any]:
    year_match = _YEAR_RE.search(html)
    year = int(year_match.group(1)) if year_match else datetime.now().year
    loc_match = _LOCATION_RE.search(html)
    name = _clean(loc_match.group(1)) if loc_match else _display_name(slug)

    merged: dict[date, set[str]] = {}

    def add(day: date | None, waste_type: str | None) -> None:
        if day is None or waste_type is None:
            return
        merged.setdefault(day, set()).add(waste_type)

    for title, items_html in _SECTION_RE.findall(html):
        waste_type = _map_section(title)
        if waste_type is None:
            continue
        for item in _DATE_ITEM_RE.findall(items_html):
            add(_parse_date(item, year), waste_type)

    for date_html, types_html in _ROW_RE.findall(html):
        day = _parse_date(date_html, year)
        for badge in _BADGE_RE.findall(types_html):
            add(day, _map_waste_label(badge))

    events = [
        {"date": day.isoformat(), "types": sorted(types)}
        for day, types in sorted(merged.items())
    ]
    return {
        "id": slug,
        "name": name,
        "url": url,
        "year": year,
        "events": events,
    }


def fallback_locations() -> list[dict[str, str]]:
    from .schedule_data import LOCATIONS

    items = []
    for key, value in LOCATIONS.items():
        items.append(
            {
                "id": key,
                "name": value["name"],
                "url": value["source"],
            }
        )
    return items


def fallback_calendar(location_id: str) -> dict[str, Any] | None:
    from .schedule_data import LOCATIONS

    location = LOCATIONS.get(location_id)
    if location is None:
        slug = location_id.replace("_", "-")
        for key, value in LOCATIONS.items():
            key_slug = key.replace("_", "-")
            if slug.startswith(key_slug) or key_slug in slug:
                location = value
                location_id = key
                break
    if location is None:
        return None
    return {
        "id": location_id,
        "name": location["name"],
        "url": location["source"],
        "year": 2026,
        "events": [
            {"date": raw_date, "types": list(types)}
            for raw_date, types in location["events"]
        ],
        "source": "local",
    }
