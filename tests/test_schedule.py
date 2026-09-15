"""Provjera transkribiranog kalendara odvoza za 2026."""

from __future__ import annotations

import sys
import types
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "murs_ekom"
PACKAGE = "murs_ekom"
if PACKAGE not in sys.modules:
    pkg = types.ModuleType(PACKAGE)
    pkg.__path__ = [str(ROOT)]
    sys.modules[PACKAGE] = pkg

from murs_ekom.schedule import (  # noqa: E402
    TYPE_ORDER,
    WASTE_TYPES,
    collection_on,
    collections_for,
    last_from,
    location_choices,
    next_collection,
    next_from,
    notify_target_date,
    when_label,
)
from murs_ekom.schedule_data import LOCATIONS  # noqa: E402


def test_locations_exist() -> None:
    choices = location_choices()
    assert "grad_mursko_sredisce" in choices
    assert len(choices) == 3


def test_all_events_are_valid_2026() -> None:
    for location_id, location in LOCATIONS.items():
        seen: set[date] = set()
        for raw_date, types in location["events"]:
            day = date.fromisoformat(raw_date)
            assert day.year == 2026, f"{location_id} {raw_date}"
            assert day not in seen, f"duplikat {location_id} {raw_date}"
            seen.add(day)
            assert types, f"prazan odvoz {location_id} {raw_date}"
            for waste_type in types:
                assert waste_type in WASTE_TYPES
                assert waste_type in TYPE_ORDER


def test_grad_next_from_15_september() -> None:
    today = date(2026, 9, 15)
    item = next_collection("grad_mursko_sredisce", today)
    assert item is not None
    assert item.date == date(2026, 9, 16)
    assert item.types == ("mixed", "bio")
    assert when_label(item, today) == "Sutra"


def test_notify_day_before_matches_tomorrow_collection() -> None:
    today = date(2026, 9, 15)
    target = notify_target_date(today, 1)
    item = collection_on("grad_mursko_sredisce", target)
    assert item is not None
    assert "bio" in item.types
    assert "mixed" in item.types


def test_christmas_trees_with_bio() -> None:
    item = collection_on("grad_mursko_sredisce", date(2026, 1, 7))
    assert item is not None
    assert "christmas_trees" in item.types
    assert "bio" in item.types


def test_christmas_trees_last_after_january() -> None:
    today = date(2026, 9, 15)
    items = collections_for("grad_mursko_sredisce")
    assert next_from(items, today, waste_type="christmas_trees") is None
    last = last_from(items, today, waste_type="christmas_trees")
    assert last is not None
    assert last.date == date(2026, 1, 21)


def test_bulky_and_branches() -> None:
    bulky = collection_on("grad_mursko_sredisce", date(2026, 2, 25))
    branches = collection_on("grad_mursko_sredisce", date(2026, 3, 18))
    assert bulky is not None and bulky.types == ("bulky",)
    assert branches is not None
    assert "branches" in branches.types
    assert "bio" in branches.types


def test_sorted_and_complete() -> None:
    items = collections_for("grad_mursko_sredisce")
    dates = [item.date for item in items]
    assert dates == sorted(dates)
    assert len(items) >= 50


def test_parse_calendar_html() -> None:
    from murs_ekom.source import parse_calendar_html

    html = """
    <p><strong>Lokacija:</strong> Grad Mursko Središće</p>
    <p><strong>Godina:</strong> 2026</p>
    <div class="kalendar-section">
        <h3>Božićna drvca — datumi odvoza</h3>
        <ul class="date-list"><li>07.01.2026</li></ul>
    </div>
    <table class="kalendar-table">
        <tr>
            <td>16.09.</td>
            <td class="waste-types">
                <span class="waste-badge">Bio otpad</span>
                <span class="waste-badge">Miješani komunalni otpad</span>
            </td>
        </tr>
    </table>
    """
    parsed = parse_calendar_html(html, slug="grad-mursko-sredisce-2026")
    by_date = {item["date"]: set(item["types"]) for item in parsed["events"]}
    assert "Sredi" in parsed["name"]
    assert by_date["2026-09-16"] == {"bio", "mixed"}
    assert "christmas_trees" in by_date["2026-01-07"]


if __name__ == "__main__":
    tests = [
        test_locations_exist,
        test_all_events_are_valid_2026,
        test_grad_next_from_15_september,
        test_notify_day_before_matches_tomorrow_collection,
        test_christmas_trees_with_bio,
        test_christmas_trees_last_after_january,
        test_bulky_and_branches,
        test_sorted_and_complete,
        test_parse_calendar_html,
    ]
    for test in tests:
        test()
        print(f"ok {test.__name__}")
    print("all passed")
