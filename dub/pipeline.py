from __future__ import annotations

from pathlib import Path
from typing import Any

from core.config import settings
from dub.subtitle_renderer import SubtitleRenderer
from dub.transcriber import Transcriber
from dub.translator import Translator


class DubPipeline:
    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or settings.output_dir
        self.transcriber = Transcriber()
        self.translator = Translator()
        self.subtitle_renderer = SubtitleRenderer()
        (self.output_dir / "transcribed").mkdir(parents=True, exist_ok=True)
        (self.output_dir / "dubbed").mkdir(parents=True, exist_ok=True)

    async def process(
        self,
        video_path: str,
        source_lang: str = "auto",
        target_lang: str = "vi",
        burn_subtitles: bool = False,
    ) -> dict[str, Any]:
        video = Path(video_path).expanduser().resolve()
        base_name = video.stem
        segments = await self.transcriber.transcribe_async(str(video), source_lang)

        original_srt = self.output_dir / "transcribed" / f"{base_name}_original.srt"
        self.transcriber.to_srt(segments, str(original_srt))

        translated_segments = await self.translator.translate_segments(segments, target_lang, source_lang)
        translated_srt = self.output_dir / "transcribed" / f"{base_name}_{target_lang}.srt"
        self.transcriber.to_srt(translated_segments, str(translated_srt))

        result: dict[str, Any] = {
            "success": True,
            "original_video": str(video),
            "original_subtitle": str(original_srt),
            "translated_subtitle": str(translated_srt),
            "segments_count": len(segments),
            "target_language": target_lang,
            "rendered_video": None,
        }

        if burn_subtitles:
            rendered = self.output_dir / "dubbed" / f"{base_name}_{target_lang}_subtitled.mp4"
            result["rendered_video"] = await self.subtitle_renderer.render(
                str(video),
                None,
                str(translated_srt),
                str(rendered),
            )

        return result
