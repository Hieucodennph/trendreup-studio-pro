from __future__ import annotations

import asyncio
from pathlib import Path

from core.utils import require_binary, run_command


class SubtitleRenderer:
    async def render(
        self,
        video_path: str,
        audio_path: str | None,
        subtitle_path: str,
        output_path: str,
    ) -> str:
        require_binary("ffmpeg")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        def work() -> None:
            subtitle_filter = str(Path(subtitle_path).resolve()).replace("\\", "/").replace(":", "\\:")
            if audio_path:
                args = [
                    "ffmpeg",
                    "-i",
                    video_path,
                    "-i",
                    audio_path,
                    "-vf",
                    f"subtitles='{subtitle_filter}'",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-shortest",
                    "-y",
                    output_path,
                ]
            else:
                args = [
                    "ffmpeg",
                    "-i",
                    video_path,
                    "-vf",
                    f"subtitles='{subtitle_filter}'",
                    "-c:a",
                    "copy",
                    "-y",
                    output_path,
                ]
            run_command(args)

        await asyncio.to_thread(work)
        return output_path
