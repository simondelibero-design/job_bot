"""Identify which ATS platform hosts a job application, from its URL."""
import re

PLATFORM_PATTERNS = {
    "greenhouse": re.compile(r"(boards|job-boards)\.greenhouse\.io", re.I),
    "lever": re.compile(r"jobs\.lever\.co", re.I),
    "workday": re.compile(r"\.myworkdayjobs\.com", re.I),
    "icims": re.compile(r"\.icims\.com", re.I),
}


def detect_platform(url: str) -> str:
    if not url:
        return "unknown"
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return "unknown"
