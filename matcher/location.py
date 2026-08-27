"""Classifies whether a job's location string is US-based — used to filter
out international postings, which a lot of company-specific ATS scrapers
(Greenhouse/Lever/Eightfold/etc. boards) pull in unfiltered. Those boards
have no location/country query param at all (documented in each scraper's
own docstring — e.g. scrapers/_greenhouse.py), so a keyword search against
a global company's board returns every office worldwide, not just US ones.
Confirmed live 2026-08-27: hundreds of active-queue jobs (Singapore,
India, China, Germany, UK, Japan, Netherlands, Canada, Mexico, and more)
had slipped through with nothing filtering them out — the existing
distance-tier system in matcher/distance.py only classifies *known US
cities* for the "local" search mode; "remote" and "life_change" modes
apply no geographic filter at all today.

Deliberately a blocklist (any country name below → not US), not a
whitelist requiring a positive US match — a whitelist would risk
excluding legitimately domestic postings with unusual/incomplete location
formatting this hasn't seen yet (e.g. a bare city name with no state).
Missing/unresolvable text defaults to US (included) for the same reason:
better to occasionally miss a foreign posting than to silently hide a
real domestic one over a formatting quirk. Add more countries here as
they show up in real discovery runs and slip through, same maintenance
pattern as matcher/distance.py's CITY_COORDS table.
"""
import re

_NON_US_COUNTRY_MARKERS = [
    # Full names and common abbreviations actually seen in real postings —
    # not an exhaustive list of every country on Earth, just what shows up
    # on the ATS platforms this project actually scrapes.
    "united kingdom", "uk", "england", "scotland", "wales", "northern ireland",
    "germany", "deutschland", "france", "netherlands", "belgium", "switzerland",
    "austria", "spain", "italy", "portugal", "ireland", "poland", "hungary",
    "czech republic", "czechia", "romania", "sweden", "norway", "finland",
    "denmark", "greece", "luxembourg",
    "india", "china", "japan", "south korea", "korea", "taiwan", "singapore",
    "malaysia", "indonesia", "thailand", "vietnam", "philippines", "hong kong",
    "australia", "new zealand", "nz",
    "canada", "brazil", "argentina", "chile", "colombia",
    "israel", "united arab emirates", "uae", "saudi arabia", "qatar", "turkey",
    "south africa", "egypt", "nigeria", "kenya",
    "russia", "ukraine",
    # "mexico" deliberately excluded from this list — see _MEXICO_RE below,
    # it needs a lookbehind guard "New Mexico" (a real US state) doesn't have.
]
# Word-boundary match so "in" (Indiana's abbreviation, or the word "in")
# doesn't false-match "india" style substrings, and "sgp"/country codes are
# still ambiguous without a boundary — matched as whole words/phrases only.
_NON_US_RE = re.compile(
    r"\b(" + "|".join(re.escape(m) for m in _NON_US_COUNTRY_MARKERS) + r")\b", re.I
)
# Confirmed live 2026-08-27: a plain "mexico" word-boundary match false-hit
# "US, New Mexico, Albuquerque" (a real US state) since "New Mexico"
# contains "Mexico" as its own whole word. Guard with a lookbehind so
# "Mexico City"/"Monterrey, Mexico" still correctly count as non-US, but
# "New Mexico" doesn't.
_MEXICO_RE = re.compile(r"(?<!new )\bmexico\b", re.I)

# Two-letter country-code suffixes seen verbatim in real scraped location
# strings (e.g. "Singapore,SGP") that a word-boundary country-name match
# won't catch on their own.
_NON_US_CODE_RE = re.compile(r",\s*(SGP|GBR|DEU|IND|CHN|JPN|KOR|AUS|CAN|MEX)\s*$", re.I)


def is_us_location(location: str | None) -> bool:
    """True unless the location string contains a clear non-US signal —
    see module docstring for why this defaults to True (US) rather than
    requiring positive proof of a US location."""
    if not location:
        return True
    if _NON_US_RE.search(location) or _NON_US_CODE_RE.search(location) or _MEXICO_RE.search(location):
        return False
    return True
