"""Search scope and priority configuration. Edit freely as your targets change."""
import json
from pathlib import Path

# User-adjustable distance/radius knobs, editable from the dashboard home
# page (under "Database") without touching this file. Falls back to the
# defaults below if the file doesn't exist yet or is malformed — never lets
# a bad settings file crash the whole config import.
SETTINGS_PATH = Path(__file__).parent / "dashboard" / "settings.json"
DEFAULT_DISTANCE_SETTINGS = {
    "close_max_miles": 10, "mid_max_miles": 20, "far_max_miles": 45,
    "life_change_radius_miles": 100,
    # Relative priority weights, one per tier — shown as a live pie chart on
    # the dashboard, driven by 4 sliders (one per tier). Each is just a raw
    # number; what matters is the *proportion* one takes up against the
    # other three, not its absolute value, so they don't need to be
    # hand-balanced to sum to 100 — normalized automatically wherever they're
    # used (see TIER_WEIGHTS / matcher/scorer.py's priority_score). A tier
    # with 0 gets no ranking boost at all. Defaults taper off with distance,
    # but every tier is independently adjustable — there's nothing stopping
    # you from weighting "far" above "close" if that's ever what you want.
    "close_weight": 40, "mid_weight": 30, "far_weight": 20, "life_change_weight": 10,
}
MAX_PROXIMITY_BONUS = 10  # comparable to the top SECTOR_WEIGHTS entries (quantum, particle accelerator: 10)


def load_distance_settings() -> dict:
    """Public so dashboard/app.py can read the live values straight off disk
    (rather than trusting this module's own import-time snapshot, which goes
    stale the moment settings.json changes without a process restart) and
    so it can reuse the same defaults/validation when saving a new value."""
    settings = dict(DEFAULT_DISTANCE_SETTINGS)
    try:
        saved = json.loads(SETTINGS_PATH.read_text())
        for key in DEFAULT_DISTANCE_SETTINGS:
            if key in saved:
                settings[key] = saved[key]
    except (OSError, json.JSONDecodeError, ValueError):
        pass  # no file yet, or it's corrupt — just use the defaults
    return settings


_distance_settings = load_distance_settings()

LOCATION = {
    "city": "Milton",
    "state": "WA",
    "query": "1410 10th Ave, Milton, WA 98354",
    # Search radius for the "local" mode sweep — kept equal to the "far"
    # tier's outer limit below, since searching further than the widest
    # tier that will ever accept a result is pointless.
    "radius_miles": _distance_settings["far_max_miles"],
}

# Distance-tiered relevance filtering: close jobs are cheap to consider, so
# we're loose about field-relevance; far jobs cost real commute time, so they
# need to actually match your fields. Checked in order, first tier whose
# max_miles covers the job's distance wins. Jobs whose location we can't
# resolve to a distance (see matcher/distance.py) default to the last tier
# ("far") — the strictest — rather than being treated as conveniently close.
# max_miles values are user-adjustable (see load_distance_settings above);
# min_score thresholds are not exposed in the UI, only the mile boundaries.
DISTANCE_TIERS = [
    {"name": "close", "max_miles": _distance_settings["close_max_miles"], "min_score": 0},
    {"name": "mid", "max_miles": _distance_settings["mid_max_miles"], "min_score": 1},
    {"name": "far", "max_miles": _distance_settings["far_max_miles"], "min_score": 3},
]

# Search radius (miles) used for the life_change mode's nationwide sweep —
# searches around the literal string "United States" as the location, so
# this barely constrains anything geographically in practice, but it's the
# actual parameter Indeed/ZipRecruiter's search API takes. User-adjustable
# from the dashboard, same mechanism as the tiers above.
LIFE_CHANGE_SEARCH_RADIUS_MILES = _distance_settings["life_change_radius_miles"]

# Keyed by the same tier-name strings score_job() already produces: "close"/
# "mid"/"far" for local-mode jobs, "life_change" for that mode (which tags
# its own tier with the mode name — see matcher/scorer.py). "remote" isn't
# one of the four weighted categories, so remote-mode jobs always get 0
# here regardless of these settings — there's no pie slice for it.
TIER_WEIGHTS = {
    "close": _distance_settings["close_weight"],
    "mid": _distance_settings["mid_weight"],
    "far": _distance_settings["far_weight"],
    "life_change": _distance_settings["life_change_weight"],
}

# Search terms sent to Indeed / ZipRecruiter. Keep these as realistic job-title
# phrases people actually search, not just field names.
SEARCH_KEYWORDS = [
    # core degree fields
    "physics", "applied physics", "engineering", "chemistry", "materials science",
    "computer science", "mathematics",
    # additional adjacent fields
    "electrical engineering", "mechanical engineering", "aerospace engineering",
    "nuclear engineering", "biomedical engineering", "environmental engineering",
    "geophysics", "metallurgy",
    # roles / job titles
    "research scientist", "research engineer", "R&D engineer", "engineering technician",
    "drafting technician", "CAD technician", "lab technician", "wet lab technician",
    "test engineer", "quality engineer", "QA engineer", "process engineer",
    "manufacturing engineer", "controls engineer", "systems engineer",
    "instrumentation engineer", "metrology technician", "calibration technician",
    "simulation engineer", "modeling engineer", "data scientist",
    "nondestructive testing technician", "NDT technician", "cleanroom technician",
    # specific domains called out
    "quantum computing", "quantum engineer", "particle accelerator",
    "accelerator physics", "aerospace engineer", "optics engineer", "photonics engineer",
    "RF engineer", "semiconductor engineer", "nanofabrication",
    # broadened: biomedical/biotech
    "biotechnology", "biomedical technician", "biotech research associate",
    "pharmaceutical scientist", "process development engineer",
    # broadened: renewable energy
    "renewable energy engineer", "solar engineer", "battery engineer",
    "energy storage engineer", "photovoltaic engineer",
    # broadened: robotics/automation
    "robotics engineer", "automation engineer", "mechatronics engineer",
    "controls technician",
    # broadened: environmental
    "environmental scientist", "environmental technician",
    "water quality technician", "environmental compliance",
    # broadened: government/defense/naval (JBLM, Bangor sub base, Puget Sound shipyard nearby)
    "defense contractor engineer", "systems integration engineer",
    "test and evaluation engineer", "naval engineer", "marine engineer",
    "shipyard engineer",
    # broadened: data/ML
    "data analyst", "data engineer", "machine learning engineer",
    # broadened: semiconductor fab depth
    "process integration engineer", "yield engineer", "fab technician",
    # round 2: civil/structural (real AutoCAD Civil 3D / drafting experience)
    "civil engineer", "structural engineer", "civil engineering technician",
    "geotechnical engineer",
    # round 2: patent/IP (real posting seen for this exact niche)
    "patent agent", "patent examiner", "technical writer", "IP paralegal",
    # round 2: acoustics/inspection (real welding/NDT background)
    "acoustics engineer", "welding inspector", "welding engineer",
    # round 2: field/technical sales (leverages communication + technical depth)
    "field application engineer", "technical sales engineer", "applications engineer",
    "sales engineer",
    # round 2: actuarial/quant (leverages math + MCM modeling background)
    "actuarial analyst", "quantitative analyst",
    # round 2: STEM education/outreach (real Club Z tutoring background)
    "stem outreach coordinator", "science education specialist", "curriculum developer",
]

# Case-insensitive substring match against title + snippet. Weight scale is
# arbitrary (higher = ranked first); tune once real results start coming in.
SECTOR_WEIGHTS = {
    "quantum": 10,
    "particle accelerator": 10,
    "accelerator physics": 10,
    "photonics": 9,
    "optics": 9,
    "aerospace": 9,
    "semiconductor": 8,
    "nanofabrication": 8,
    "materials science": 8,
    "materials scientist": 8,
    "physics": 8,
    "physicist": 8,
    "nuclear": 7,
    "rf engineer": 7,
    "metrology": 7,
    "instrumentation": 7,
    "wet lab": 7,
    "r&d": 7,
    "research scientist": 7,
    "research engineer": 7,
    "chemistry": 6,
    "chemist": 6,
    "computer science": 5,
    "data scientist": 5,
    "mathematics": 5,
    "mechanical engineer": 5,
    "electrical engineer": 5,
    "systems engineer": 5,
    "test engineer": 4,
    "quality engineer": 4,
    "process engineer": 4,
    "controls engineer": 4,
    "manufacturing engineer": 4,
    "simulation": 4,
    "engineering technician": 3,
    "drafting technician": 3,
    "cad technician": 3,
    "lab technician": 3,
    "calibration technician": 3,
    "cleanroom technician": 3,
    "ndt": 3,
    "nondestructive testing": 3,
    # broadened categories
    "battery": 7,
    "energy storage": 7,
    "renewable energy": 7,
    "machine learning": 6,
    "robotics": 6,
    "mechatronics": 6,
    "biotechnology": 6,
    "biomedical": 6,
    "defense": 6,
    "naval": 6,
    "marine engineer": 6,
    "shipyard": 6,
    "solar": 6,
    "photovoltaic": 6,
    "automation": 5,
    "environmental science": 5,
    "environmental engineer": 5,
    "systems integration": 5,
    "test and evaluation": 5,
    "process integration": 5,
    "yield engineer": 5,
    "pharmaceutical": 5,
    "data analyst": 4,
    "data engineer": 4,
    "fab technician": 4,
    # round 2
    "civil engineer": 6,
    "structural engineer": 6,
    "geotechnical engineer": 6,
    "patent agent": 6,
    "patent examiner": 6,
    "acoustics engineer": 6,
    "actuarial analyst": 5,
    "quantitative analyst": 5,
    "welding inspector": 5,
    "welding engineer": 5,
    "field application engineer": 5,
    "technical sales engineer": 5,
    "applications engineer": 5,
    "sales engineer": 4,
    "civil engineering technician": 4,
    "technical writer": 4,
    "stem outreach": 4,
    "science education": 4,
    "curriculum developer": 3,
}

# Applied against title + snippet; any match drops the score to 0 and flags
# the job as excluded rather than deleting it (keeps the log complete).
# Unrelated to the PhD system below — this is for things like unpaid roles,
# plus other categorical credential gates a bachelor's-level applicant can't
# clear regardless of field-relevance score. "Medical Physicist" specifically
# requires a CAMPEP-accredited graduate program + board certification — it
# scores high on "physics" keyword match but is realistically unreachable,
# and (unlike the PhD-only roles) the postings never say "PhD" so the PhD
# system doesn't catch them. Same logic for PE-licensed and MD-required roles.
EXCLUDE_KEYWORDS = [
    "unpaid", "internship, no pay", "commission only",
    # credential-gated roles (not PhD-specific, so not part of the PHD_* lists)
    "medical physicist", "board certified physicist", "campep accredited",
    "professional engineer license required", "pe license required",
    "active professional license required", "medical residency required",
    "completion of residency required", "licensed physician required",
    "md required",
]

# Three-tier PhD system, checked in this order — first match wins, no
# overlap. A job with zero PhD-related language is untouched by any of this.
#   1. PHD_REQUIRED_KEYWORDS  -> phd_flag "excluded"       (hard-excluded, hidden)
#   2. PHD_PREFERRED_KEYWORDS -> phd_flag "semi_excluded"  (soft signal, own tab)
#   3. bare "phd"/"ph.d" mention not caught above -> phd_flag "likely_excluded" (own tab)
# "(ph.d.)" / "(phd)" as a title suffix is a strong, common real-world
# convention (seen live: "Metallurgical Engineer (Ph.D.)", "Manager,
# Materials Science (Ph.D.)") for roles that are PhD-only.
PHD_REQUIRED_KEYWORDS = [
    "phd required", "ph.d. required", "doctorate required",
    "requires a phd", "requires a ph.d", "phd or equivalent required",
    "doctoral degree required", "(ph.d.)", "(phd)",
    # "postdoc" titles categorically require an already-completed PhD, even
    # when the posting never spells out "PhD" as a word.
    "postdoctoral", "post-doctoral", "postdoc",
]
PHD_PREFERRED_KEYWORDS = [
    "phd preferred", "ph.d. preferred", "phd a plus", "phd is a plus",
    "phd desired", "doctorate preferred", "preferably phd", "phd strongly preferred",
]

# Seniority-level filtering: routed into the same "likely_excluded" tab as a
# bare PhD mention (not because these imply a PhD — just reusing the same
# low-priority "flagged but still visible, one-click Restore" bucket instead
# of building a separate one). Matched whole-word, case-insensitive, only
# checked if the job wasn't already PhD-flagged above.
# Real false-positive risk on two of these, given this user's fields: "lead"
# also means the metal (lead-free, lead paint testing, lead time — plausible
# in materials/environmental postings), and "sr" collides with unrelated
# abbreviations (SR-71, State Route — plausible in aerospace/defense
# postings). Watch the likely_excluded tab and Restore anything caught by
# mistake rather than assuming the filter is always right.
SENIORITY_EXCLUDE_KEYWORDS = ["head", "lead", "senior", "sr", "chief"]

MIN_SCORE_TO_QUEUE = 3  # kept for the "far" distance tier's threshold

# Remote sweep: no natural distance cap since it's not geography-limited, so
# it needs its own high-selectivity bar instead of the distance tiers.
REMOTE_MIN_SCORE = 9

# life_change sweep: nationwide, relocation-open, filtered on both real
# field-relevance AND pay. "specialization" = SEARCH_KEYWORDS above — the
# same growing list used everywhere else, not a separate list to maintain.
LIFE_CHANGE_MIN_SCORE = 6
LIFE_CHANGE_MIN_SALARY = 90000  # estimated annual; see matcher/salary.py
