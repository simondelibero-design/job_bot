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
    "successfactors": re.compile(r"\.successfactors\.(com|eu)", re.I),
}


def detect_platform(url: str) -> str:
    if not url:
        return "unknown"
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return "unknown"
