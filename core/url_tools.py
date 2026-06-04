from __future__ import annotations

import re


PLATFORM_PATTERNS: dict[str, list[str]] = {
    "youtube": ["youtube.com", "youtu.be"],
    "tiktok": ["tiktok.com"],
    "douyin": ["douyin.com", "iesdouyin.com", "v.douyin.com"],
    "rednote": ["xiaohongshu.com", "xhslink.com"],
    "instagram": ["instagram.com", "instagr.am"],
    "facebook": ["facebook.com", "fb.watch", "fb.com"],
    "kwai": ["kwai.com", "kuaishou.com"],
    "likee": ["likee.video", "likee.com"],
    "twitter": ["twitter.com", "x.com"],
}


def extract_first_url(value: str) -> str:
    match = re.search(r"https?://[^\s<>'\"]+", value.strip())
    return match.group(0).rstrip(").,;") if match else value.strip()


def detect_platform(url: str) -> str:
    url_lower = url.lower()
    for platform, domains in PLATFORM_PATTERNS.items():
        if any(domain in url_lower for domain in domains):
            return platform
    return "auto"
