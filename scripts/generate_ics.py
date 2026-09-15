"""Generira ICS kalendare iz transkribiranog rasporeda."""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "murs_ekom"
if "murs_ekom" not in sys.modules:
    pkg = types.ModuleType("murs_ekom")
    pkg.__path__ = [str(PKG)]
    sys.modules["murs_ekom"] = pkg

from murs_ekom.schedule import collections_for, location_choices  # noqa: E402


def _fold(line: str) -> str:
    return line


def build_ics(location_id: str) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//MURS-EKOM//Odvoz smeća 2026//HR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:Odvoz smeća — {location_choices()[location_id]}",
        "X-WR-TIMEZONE:Europe/Zagreb",
    ]
    for item in collections_for(location_id):
        start = item.date.strftime("%Y%m%d")
        end = item.date.fromordinal(item.date.toordinal() + 1).strftime("%Y%m%d")
        uid = f"{location_id}-{item.date.isoformat()}@murs-ekom"
        desc = "Spremnik iznesite do 6:00 ujutro."
        if "bulky" in item.types:
            desc += " Glomazni otpad prijavite na 040/543-314 najkasnije 2 dana prije."
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTART;VALUE=DATE:{start}",
                f"DTEND;VALUE=DATE:{end}",
                f"SUMMARY:{item.label}",
                f"DESCRIPTION:{desc}",
                f"LOCATION:{location_choices()[location_id]}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def main() -> None:
    out_dir = ROOT / "calendars"
    out_dir.mkdir(exist_ok=True)
    for location_id in location_choices():
        path = out_dir / f"{location_id}_2026.ics"
        path.write_text(build_ics(location_id), encoding="utf-8")
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
