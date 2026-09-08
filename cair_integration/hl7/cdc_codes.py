"""Map ClaudMD DataGroups descriptions to CDC CDCREC codes for HL7."""

from __future__ import annotations

# Keyed by normalized description from dbo.DataGroups.Description
RACE_DESCRIPTION_TO_CDCREC: dict[str, tuple[str, str]] = {
    "american indian or alaska native": ("1002-5", "American Indian or Alaska Native"),
    "asian": ("2028-9", "Asian"),
    "black or african american": ("2054-5", "Black or African American"),
    "native hawaiian or other pacific islander": ("2076-8", "Native Hawaiian or Other Pacific Islander"),
    "white": ("2106-3", "White"),
    "other race": ("2131-1", "Other Race"),
    "unknown": ("UNK", "Unknown"),
}

ETHNIC_DESCRIPTION_TO_CDCREC: dict[str, tuple[str, str]] = {
    "hispanic or latino": ("2135-2", "Hispanic or Latino"),
    "not hispanic or latino": ("2186-5", "Not Hispanic or Latino"),
    "unknown": ("UNK", "Unknown"),
}


def map_race(description: str) -> tuple[str, str]:
    if not description:
        return "", ""
    return RACE_DESCRIPTION_TO_CDCREC.get(description.strip().lower(), ("", description.strip()))


def map_ethnicity(description: str) -> tuple[str, str]:
    if not description:
        return "", ""
    return ETHNIC_DESCRIPTION_TO_CDCREC.get(description.strip().lower(), ("", description.strip()))
