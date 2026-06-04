from __future__ import annotations

import hashlib
import random
from typing import Any


class TrendCrawler:
    platforms = ["youtube", "tiktok", "douyin", "instagram", "facebook", "rednote"]

    def _stable_rng(self, keyword: str, platform: str) -> random.Random:
        seed = int(hashlib.sha256(f"{keyword}:{platform}".encode("utf-8")).hexdigest()[:12], 16)
        return random.Random(seed)

    def search(self, keyword: str, platforms: list[str] | None = None, max_results: int = 5) -> list[dict[str, Any]]:
        selected = platforms or ["youtube", "tiktok", "douyin"]
        results: list[dict[str, Any]] = []
        for platform in selected:
            if platform not in self.platforms:
                continue
            rng = self._stable_rng(keyword, platform)
            for index in range(max_results):
                views = rng.randint(10_000, 4_000_000)
                likes = rng.randint(500, max(1000, views // 8))
                comments = rng.randint(20, max(200, views // 100))
                shares = rng.randint(10, max(100, views // 150))
                trend_score = min(100, round((views / 50_000) + (likes / 5_000) + rng.uniform(35, 70), 2))
                video_id = hashlib.md5(f"{keyword}:{platform}:{index}".encode("utf-8")).hexdigest()[:11]
                results.append(
                    {
                        "title": f"[{platform.title()}] {keyword} - viral angle {index + 1}",
                        "description": f"Seeded trend candidate for {keyword} on {platform}.",
                        "video_url": self._url_for(platform, keyword, video_id),
                        "thumbnail_url": "",
                        "source_platform": platform,
                        "author": f"{platform}_creator_{index + 1}",
                        "view_count": views,
                        "like_count": likes,
                        "comment_count": comments,
                        "share_count": shares,
                        "duration": rng.randint(15, 720),
                        "trend_score": trend_score,
                        "keyword": keyword,
                    }
                )
        return sorted(results, key=lambda item: item["trend_score"], reverse=True)

    def crawl_ideas(self, ideas: list[dict[str, Any]], platforms: list[str] | None = None, max_per_idea: int = 3) -> list[dict[str, Any]]:
        all_results: list[dict[str, Any]] = []
        for idea in ideas:
            idea_platforms = platforms
            if not idea_platforms and idea.get("platform_filter") and idea["platform_filter"] != "all":
                idea_platforms = [item.strip() for item in idea["platform_filter"].split(",") if item.strip()]
            results = self.search(idea["name"], idea_platforms, max_per_idea)
            for result in results:
                result["idea_id"] = idea["id"]
                result["idea_name"] = idea["name"]
            all_results.extend(results)
        return all_results

    def hashtags(self) -> list[dict[str, Any]]:
        return [
            {"name": "#xuhuong", "score": 98, "platform": "tiktok"},
            {"name": "#fyp", "score": 96, "platform": "tiktok"},
            {"name": "#learnontiktok", "score": 85, "platform": "tiktok"},
            {"name": "#technology", "score": 82, "platform": "youtube"},
            {"name": "#travel", "score": 78, "platform": "all"},
            {"name": "#cooking", "score": 76, "platform": "all"},
        ]

    def _url_for(self, platform: str, keyword: str, video_id: str) -> str:
        slug = keyword.replace(" ", "-").replace("#", "")
        if platform == "youtube":
            return f"https://youtube.com/watch?v={video_id}"
        if platform == "tiktok":
            return f"https://www.tiktok.com/@{slug}/video/{video_id}"
        if platform == "douyin":
            return f"https://www.douyin.com/video/{video_id}"
        if platform == "instagram":
            return f"https://www.instagram.com/reel/{video_id}/"
        if platform == "facebook":
            return f"https://www.facebook.com/reel/{video_id}"
        if platform == "rednote":
            return f"https://www.xiaohongshu.com/explore/{video_id}"
        return f"https://example.com/{platform}/{video_id}"
