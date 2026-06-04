from __future__ import annotations

import asyncio
from typing import Any

import requests

from core.config import settings


class Translator:
    def __init__(self, endpoint: str | None = None, api_key: str | None = None):
        self.endpoint = (endpoint if endpoint is not None else settings.libretranslate_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.libretranslate_api_key

    def translate_text(self, text: str, target_lang: str = "vi", source_lang: str = "auto") -> str:
        if not text.strip():
            return text
        if not self.endpoint:
            return text if target_lang in ("auto", source_lang) else f"[{target_lang}] {text}"

        payload: dict[str, Any] = {
            "q": text,
            "source": source_lang or "auto",
            "target": target_lang,
            "format": "text",
        }
        if self.api_key:
            payload["api_key"] = self.api_key
        response = requests.post(f"{self.endpoint}/translate", json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("translatedText") or text

    async def translate_segments(
        self,
        segments: list[dict[str, Any]],
        target_lang: str = "vi",
        source_lang: str = "auto",
    ) -> list[dict[str, Any]]:
        async def translate_one(segment: dict[str, Any]) -> dict[str, Any]:
            translated = await asyncio.to_thread(
                self.translate_text,
                segment["text"],
                target_lang,
                source_lang,
            )
            return {**segment, "text": translated}

        return [await translate_one(segment) for segment in segments]
