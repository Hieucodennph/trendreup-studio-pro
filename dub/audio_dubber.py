from __future__ import annotations

import asyncio

from core.utils import require_binary, run_command


class AudioDubber:
    async def mix_audio(
        self,
        video_path: str,
        dub_audio_path: str,
        output_audio_path: str,
        original_volume: float = 0.2,
        dub_volume: float = 1.0,
    ) -> str:
        require_binary("ffmpeg")

        def work() -> None:
            run_command(
                [
                    "ffmpeg",
                    "-i",
                    video_path,
                    "-i",
                    dub_audio_path,
                    "-filter_complex",
                    f"[0:a]volume={original_volume}[a0];[1:a]volume={dub_volume}[a1];[a0][a1]amix=inputs=2:duration=longest",
                    "-y",
                    output_audio_path,
                ]
            )

        await asyncio.to_thread(work)
        return output_audio_path
