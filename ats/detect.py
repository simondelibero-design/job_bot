"""Identify which ATS platform hosts a job application, from its URL."""
import re

PLATFORM_PATTERNS = {
    "greenhouse": re.compile(r"(boards|job-boards)\.greenhouse\.io", re.I),
    "lever": re.compile(r"jobs\.lever\.co", re.I),
    "workday": re.compile(r"\.myworkdayjobs\.com", re.I),
    "icims": re.compile(r"\.icims\.com", re.I),
    "jazzhr": re.compile(r"\.applytojob\.com", re.I),
    "smartrecruiters": re.compile(r"\.smartrecruiters\.com", re.I),
    "taleo": re.compile(r"\.taleo\.net", re.I),
    "successfactors": re.compile(
        r"\.successfactors\.(com|eu)"
        # Several SuccessFactors "Jobs2Web" tenants front the platform with
        # their own branded domain rather than the raw successfactors.com
        # host — same situation ornl/lanl/slac/snl below needed one-off
        # patterns for. Confirmed live 2026-08-26 via scrapers/corning.py,
        # halliburton.py, oxford_instruments.py, stratasys.py.
        r"|corningjobs\.corning\.com|jobs\.halliburton\.com"
        r"|jobs\.oxinst\.com|careers\.stratasys\.com",
        re.I,
    ),
    "aps": re.compile(r"apsphysicsjobs\.com", re.I),
    "lanl": re.compile(r"lanl\.jobs", re.I),
    "ornl": re.compile(r"jobs\.ornl\.gov", re.I),
    "slac": re.compile(r"careersearch\.stanford\.edu", re.I),
    "snl": re.compile(r"sandia\.gov", re.I),
}


def detect_platform(url: str) -> str:
    if not url:
        return "unknown"
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return "unknown"


# Platforms whose ats/ handler actually fills the real application form with
# no structural gate in the way — no account creation required, no CAPTCHA
# blocking access to the fields themselves (a CAPTCHA on the final submit
# button doesn't count against this — every fully-fillable form here has
# one, it's still the human's job to solve regardless). See each handler's
# docstring for what was actually verified live before it landed here.
#
# smartrecruiters is deliberately NOT included even though ats/smartrecruiters.py
# can fill its form in principle: SmartRecruiters' own bot detection blocked
# every attempt to even reach the form this session (see that file's
# docstring), so in current practice it does not satisfy "can actually be
# filled out." icims/slac only ever get a single field (email) pre-filled
# before hitting a real gate, so they're partial, not "fully filled."
# workday/taleo/successfactors/ornl/lanl/snl are pure gate-detectors — no
# field gets filled at all.
EASY_APPLY_PLATFORMS = {"greenhouse", "lever", "jazzhr", "aps"}


def is_easy_apply(url: str) -> bool:
    return detect_platform(url) in EASY_APPLY_PLATFORMS
