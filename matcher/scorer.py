import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from config import (
    DISTANCE_TIERS, DISTANCE_WEIGHT_PERCENT, EXCLUDE_KEYWORDS, LIFE_CHANGE_MIN_SALARY,
    LIFE_CHANGE_MIN_SCORE, MAX_PROXIMITY_BONUS, PHD_PREFERRED_KEYWORDS, PHD_REQUIRED_KEYWORDS,
    REMOTE_MIN_SCORE, SECTOR_WEIGHTS, SENIORITY_EXCLUDE_KEYWORDS,
)
from matcher.distance import estimate_distance_miles
from matcher.salary import parse_salary_annual

_PHD_MENTION_RE = re.compile(r"\bph\.?\s?d\.?\b", re.I)
_SENIORITY_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in SENIORITY_EXCLUDE_KEYWORDS) + r")\b", re.I
)


def classify_distance(location: str | None) -> tuple[float | None, str]:
    """Returns (distance_miles, tier_name). Unresolvable locations default
    to the last (strictest) tier rather than being treated as close."""
    miles = estimate_distance_miles(location)
    if miles is None:
        return None, DISTANCE_TIERS[-1]["name"]
    for tier in DISTANCE_TIERS:
        if miles <= tier["max_miles"]:
            return miles, tier["name"]
    return miles, DISTANCE_TIERS[-1]["name"]


def _tier_min_score(tier_name: str) -> float:
    for tier in DISTANCE_TIERS:
        if tier["name"] == tier_name:
            return tier["min_score"]
    return DISTANCE_TIERS[-1]["min_score"]


def priority_score(score: float, distance_miles: float | None) -> float:
    """career-field score, plus a distance-proximity bonus layered on top —
    never a replacement for the field-relevance score above, which is what
    the exclusion gates in score_job() actually check. Only meaningful for
    "local" mode jobs with a resolved distance; remote/life_change jobs
    (distance_miles is always None for those) and unresolvable locations
    get no bonus, so priority_score == score for them regardless of the
    DISTANCE_WEIGHT_PERCENT setting.

    At weight 0%: identical to score (distance has no effect on ranking).
    At weight 100%: a job right at the home address gets the full
    MAX_PROXIMITY_BONUS added; a job at or beyond the "far" tier's outer
    limit gets none. Linear in between."""
    if distance_miles is None:
        return score
    far_max_miles = DISTANCE_TIERS[-1]["max_miles"]
    if far_max_miles <= 0:
        return score
    proximity_fraction = max(0.0, 1 - (distance_miles / far_max_miles))
    bonus = (DISTANCE_WEIGHT_PERCENT / 100) * MAX_PROXIMITY_BONUS * proximity_fraction
    return score + bonus


def _phd_and_sector_pass(text: str) -> dict | None:
    """Runs the shared EXCLUDE_KEYWORDS + three-tier PhD system + sector
    scoring, common to every search mode. Returns a completed result dict if
    the job is hard-excluded or PhD-flagged (semi/likely) — those outcomes
    are mode-independent — or None if the caller still needs to apply its
    own mode-specific relevance gate to score/matched."""
    for term in EXCLUDE_KEYWORDS:
        if term.lower() in text:
            return {"score": 0.0, "matched": [f"excluded: {term}"], "excluded": True, "phd_flag": None}

    for term in PHD_REQUIRED_KEYWORDS:
        if term.lower() in text:
            return {"score": 0.0, "matched": [f"excluded: {term}"], "excluded": True, "phd_flag": "excluded"}

    phd_flag = None
    phd_reason = None
    for term in PHD_PREFERRED_KEYWORDS:
        if term.lower() in text:
            phd_flag = "semi_excluded"
            phd_reason = f"phd preferred signal: {term}"
            break
    if phd_flag is None:
        m = _PHD_MENTION_RE.search(text)
        if m:
            phd_flag = "likely_excluded"
            start, end = max(m.start() - 20, 0), min(m.end() + 20, len(text))
            phd_reason = f"mentions PhD: \"...{text[start:end].strip()}...\""

    if phd_flag is None:
        m = _SENIORITY_RE.search(text)
        if m:
            phd_flag = "likely_excluded"
            start, end = max(m.start() - 20, 0), min(m.end() + 20, len(text))
            phd_reason = f"seniority term: \"...{text[start:end].strip()}...\""

    score = 0.0
    matched = []
    for term, weight in SECTOR_WEIGHTS.items():
        if term.lower() in text:
            score += weight
            matched.append(term)

    if phd_flag in ("semi_excluded", "likely_excluded"):
        return {
            "score": score, "matched": [phd_reason] + matched, "excluded": True,
            "phd_flag": phd_flag,
        }

    return None  # not excluded/flagged yet — caller applies its own gate to (score, matched)


def score_job(title: str, snippet: str = "", location: str | None = None,
              mode: str = "local", salary: str | None = None) -> dict:
    """Scores a job against SECTOR_WEIGHTS and the PhD tri-state system,
    then applies a mode-specific relevance gate:
      - "local": distance-tiered (close/mid/far from home base)
      - "remote": flat high-selectivity score threshold, no geography
      - "life_change": score threshold AND a minimum estimated salary
    Returns: score, matched, excluded, phd_flag, distance_miles, tier,
    salary_annual_est, priority_score (score plus a distance-proximity
    bonus — see priority_score() above — this is what the queue sorts by,
    score itself stays pure field-relevance for the exclusion gates)."""
    text = f"{title} {snippet}".lower()

    if mode == "local":
        distance_miles, tier = classify_distance(location)
    else:
        distance_miles, tier = None, mode  # tag with the mode name for display

    salary_annual_est = parse_salary_annual(salary)

    shared = _phd_and_sector_pass(text)
    if shared is not None:
        shared["distance_miles"] = distance_miles
        shared["tier"] = tier
        shared["salary_annual_est"] = salary_annual_est
        shared["priority_score"] = priority_score(shared["score"], distance_miles)
        return shared

    # Recompute score/matched (cheap, avoids threading extra state through
    # _phd_and_sector_pass just for the non-excluded path).
    score = 0.0
    matched = []
    for term, weight in SECTOR_WEIGHTS.items():
        if term.lower() in text:
            score += weight
            matched.append(term)

    if mode == "remote":
        excluded = score < REMOTE_MIN_SCORE
        if excluded:
            matched = matched + [f"excluded: below remote high-selectivity threshold (score {score:.0f} < {REMOTE_MIN_SCORE})"]
    elif mode == "life_change":
        excluded = score < LIFE_CHANGE_MIN_SCORE
        if excluded:
            matched = matched + [f"excluded: below life_change relevance threshold (score {score:.0f} < {LIFE_CHANGE_MIN_SCORE})"]
        elif salary_annual_est is None:
            excluded = True
            matched = matched + ["excluded: no salary listed — life_change requires a confirmed high-paying figure"]
        elif salary_annual_est < LIFE_CHANGE_MIN_SALARY:
            excluded = True
            matched = matched + [f"excluded: est. ${salary_annual_est:,.0f}/yr below life_change floor (${LIFE_CHANGE_MIN_SALARY:,.0f})"]
    else:  # local
        min_score = _tier_min_score(tier)
        excluded = score < min_score
        if excluded:
            reason = f"excluded: below {tier}-tier threshold (score {score:.0f} < {min_score:.0f}"
            reason += f", ~{distance_miles:.0f}mi)" if distance_miles is not None else ", distance unknown)"
            matched = matched + [reason]

    return {
        "score": score, "matched": matched, "excluded": excluded,
        "phd_flag": None, "distance_miles": distance_miles, "tier": tier,
        "salary_annual_est": salary_annual_est,
        "priority_score": priority_score(score, distance_miles),
    }
