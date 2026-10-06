"""Countries Energy-Charts publishes carbon intensity for.

Checked against the live API on 2026-10-06: these 26 answer /co2eq; Romania and the UK
return 404.
"""

from __future__ import annotations

from typing import Final

ZONES: Final[dict[str, str]] = {
    "at": "Austria",
    "be": "Belgium",
    "bg": "Bulgaria",
    "ch": "Switzerland",
    "cz": "Czechia",
    "de": "Germany",
    "dk": "Denmark",
    "ee": "Estonia",
    "es": "Spain",
    "fi": "Finland",
    "fr": "France",
    "gr": "Greece",
    "hr": "Croatia",
    "hu": "Hungary",
    "ie": "Ireland",
    "it": "Italy",
    "lt": "Lithuania",
    "lu": "Luxembourg",
    "lv": "Latvia",
    "nl": "Netherlands",
    "no": "Norway",
    "pl": "Poland",
    "pt": "Portugal",
    "se": "Sweden",
    "si": "Slovenia",
    "sk": "Slovakia",
}
