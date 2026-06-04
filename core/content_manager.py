from __future__ import annotations

import re


class ContentManager:
    hashtag_map = {
        "general": "#xuhuong #trending #fyp #viral",
        "technology": "#technology #tech #innovation #ai",
        "finance": "#finance #money #business #investing",
        "food": "#food #cooking #delicious #recipe",
        "travel": "#travel #adventure #explore #wanderlust",
        "beauty": "#beauty #skincare #fashion #makeup",
        "education": "#education #learning #study #knowledge",
        "funny": "#funny #comedy #humor #viral",
    }

    corrections = {
        " ko ": " khong ",
        " dc ": " duoc ",
        " vs ": " voi ",
        " r ": " roi ",
        " wa ": " qua ",
        "hum": "khong",
    }

    def auto_edit(self, original_text: str, category: str = "general", max_length: int = 2200) -> dict[str, str]:
        text = re.sub(r"http\S+", "", original_text).strip()
        text = re.sub(r"\s+", " ", text)
        padded = f" {text} "
        for wrong, correct in self.corrections.items():
            padded = padded.replace(wrong, correct)
        text = padded.strip()
        hashtags = self.hashtag_map.get(category, self.hashtag_map["general"])
        edited = f"{text}\n\n{hashtags}".strip()
        if len(edited) > max_length:
            edited = edited[: max_length - 3].rstrip() + "..."
        return {
            "original": original_text,
            "edited": edited,
            "category": category,
            "hashtags": hashtags,
        }
