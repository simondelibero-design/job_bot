"""Rough salary normalization for threshold comparisons — takes whatever
Indeed/ZipRecruiter show ("$101,600 - $152,400 a year", "$26.88 - $34.33 an
hour", "$80 - $140/hr") and estimates a single annual figure (midpoint of a
range, hourly converted at 2080 hrs/year). This is an estimate for ranking
and filtering, not a precise figure.
"""
import re

_HOURLY_RE = re.compile(r"(an hour|/hr|per hour|\bhr\b)", re.I)


def parse_salary_annual(salary: str | None) -> float | None:
    if not salary:
        return None
    # Must start with a digit — `[\d,]+` alone also matches a bare comma
    # (e.g. a scraped salary like ", DOE" or a stray "$,"), which crashed
    # float("") live during a full sweep (2026-08-26).
    numbers = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", salary)]
    if not numbers:
        return None
    midpoint = sum(numbers) / len(numbers)
    if _HOURLY_RE.search(salary):
        midpoint *= 2080
    return round(midpoint)
