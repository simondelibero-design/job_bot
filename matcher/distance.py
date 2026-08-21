"""Estimates distance in miles from home base (1410 10th Ave, Milton, WA
98354) for a job's location string, using a static table of known Puget
Sound-area city coordinates (no external geocoding API — keeps this fast,
free, and independent of rate limits).

Add more cities to CITY_COORDS as new locations show up in real discovery
runs and fail to resolve (unresolved locations default to the strictest
distance tier — see matcher/scorer.py — so nothing slips through as falsely
"close" just because it's missing from this table).
"""
from math import atan2, cos, radians, sin, sqrt

# City-level approximation for 1410 10th Ave, Milton, WA 98354 — this table
# only resolves at city granularity, so street-level precision isn't
# available (or needed) for the distance tiers.
ORIGIN_COORDS = (47.2440, -122.3121)

CITY_COORDS = {
    "milton, wa": (47.2440, -122.3121),
    "tacoma, wa": (47.2529, -122.4443),
    "ruston, wa": (47.2879, -122.5188),
    "university place, wa": (47.2343, -122.5493),
    "lakewood, wa": (47.1718, -122.5185),
    "puyallup, wa": (47.1854, -122.2929),
    "federal way, wa": (47.3223, -122.3126),
    "auburn, wa": (47.3073, -122.2285),
    "dupont, wa": (47.1004, -122.6432),
    "spanaway, wa": (47.1046, -122.4351),
    "gig harbor, wa": (47.3301, -122.5801),
    "des moines, wa": (47.4004, -122.3241),
    "burien, wa": (47.4704, -122.3467),
    "kent, wa": (47.3809, -122.2348),
    "renton, wa": (47.4829, -122.2171),
    "seatac, wa": (47.4444, -122.3009),
    "olympia, wa": (47.0379, -122.9007),
    "lacey, wa": (47.0343, -122.8232),
    "bremerton, wa": (47.5673, -122.6329),
    "shelton, wa": (47.2154, -123.1004),
    "seattle, wa": (47.6062, -122.3321),
    "bellevue, wa": (47.6101, -122.2015),
    "redmond, wa": (47.6740, -122.1215),
    "kirkland, wa": (47.6769, -122.2060),
    "bothell, wa": (47.7623, -122.2054),
    "issaquah, wa": (47.5301, -122.0326),
    "everett, wa": (47.9790, -122.2021),
    "mercer island, wa": (47.5707, -122.2221),
    "joint base lewis-mcchord, wa": (47.0742, -122.5750),
    "joint base lewis mcchord, wa": (47.0742, -122.5750),
    "jblm, wa": (47.0742, -122.5750),
    "fort lewis, wa": (47.0742, -122.5750),
    "bangor, wa": (47.7379, -122.7215),  # Naval Base Kitsap-Bangor
    "silverdale, wa": (47.6446, -122.6929),
}

# Sort longest-key-first so "joint base lewis-mcchord, wa" matches before a
# shorter accidental substring would. Matched as a substring anywhere in the
# (lowercased) location string, so prefixes like "Hybrid work in Seattle, WA
# 98101" or suffixes like "(Georgetown area)" don't break resolution the way
# a strict leading regex extraction would.
_SORTED_CITY_KEYS = sorted(CITY_COORDS.keys(), key=len, reverse=True)


def _parse_city_state(location: str) -> str | None:
    if not location:
        return None
    text = location.lower()
    for key in _SORTED_CITY_KEYS:
        if key in text:
            return key
    return None


def _haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, [*a, *b])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 3958.8 * atan2(sqrt(h), sqrt(1 - h))  # 3958.8 = Earth radius in miles


def estimate_distance_miles(location: str | None) -> float | None:
    key = _parse_city_state(location or "")
    if key is None or key not in CITY_COORDS:
        return None
    return round(_haversine_miles(ORIGIN_COORDS, CITY_COORDS[key]), 1)
