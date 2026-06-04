from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from core.config import settings
from core.utils import require_binary, resolve_existing_file, run_command


class Transcriber:
    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
    ):
        self.model_size = model_size or settings.whisper_model
        self.device = device or settings.whisper_device
        self.compute_type = compute_type or settings.whisper_compute_type
        self.model: Any | None = None

    def _load_model(self) -> None:
        if self.model is not None:
            return
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Install it with: pip install faster-whisper"
            ) from exc
        self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)

    def extract_audio(self, video_path: str, audio_path: str | None = None) -> str:
        source = resolve_existing_file(video_path)
        require_binary("ffmpeg")
        target = Path(audio_path) if audio_path else source.with_suffix(".studio.wav")
        run_command(
            [
                "ffmpeg",
                "-i",
                str(source),
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-y",
                str(target),
            ]
        )
        return str(target)

    def transcribe(self, video_path: str, language: str = "auto") -> list[dict[str, Any]]:
        self._load_model()
        audio_path = self.extract_audio(video_path)
        try:
            kwargs: dict[str, Any] = {"beam_size": 5, "vad_filter": True}
            if language and language != "auto":
                kwargs["language"] = language
            segments, _info = self.model.transcribe(audio_path, **kwargs)
            return [
                {"start": float(segment.start), "end": float(segment.end), "text": segment.text.strip()}
                for segment in segments
                if segment.text.strip()
            ]
        finally:
            Path(audio_path).unlink(missing_ok=True)

    async def transcribe_async(self, video_path: str, language: str = "auto") -> list[dict[str, Any]]:
        return await asyncio.to_thread(self.transcribe, video_path, language)

    def to_srt(self, segments: list[dict[str, Any]], output_path: str) -> str:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        def format_time(seconds: float) -> str:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millis = int(round((seconds - int(seconds)) * 1000))
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

        with target.open("w", encoding="utf-8") as handle:
            for index, segment in enumerate(segments, 1):
                handle.write(f"{index}\n")
                handle.write(f"{format_time(segment['start'])} --> {format_time(segment['end'])}\n")
                handle.write(f"{segment['text']}\n\n")
        return str(target)
