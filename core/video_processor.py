from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from core.config import settings
from core.utils import require_binary, resolve_existing_file, run_command, safe_filename


class VideoProcessor:
    async def process(
        self,
        input_path: str,
        mode: str = "anti_detect",
        output_dir: Path | None = None,
        watermark_text: str = "",
        speed: float = 1.0,
        mirror: bool = False,
        compress: bool = True,
    ) -> dict[str, Any]:
        require_binary("ffmpeg")
        source = resolve_existing_file(input_path)
        target_dir = output_dir or settings.output_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / f"{safe_filename(source.stem)}_{mode}.mp4"

        filters: list[str] = []
        if mode == "anti_detect" or mirror:
            filters.append("hflip" if mirror else "eq=brightness=0.015:saturation=1.04")
        if watermark_text:
            escaped = watermark_text.replace(":", "\\:").replace("'", "\\'")
            filters.append(f"drawtext=text='{escaped}':x=20:y=h-th-24:fontcolor=white:fontsize=24:box=1:boxcolor=black@0.35")
        vf = ",".join(filters) if filters else "null"

        args = ["ffmpeg", "-i", str(source), "-vf", vf]
        if speed and abs(speed - 1.0) > 0.001:
            args.extend(["-filter:a", f"atempo={max(0.5, min(2.0, speed))}"])
            if vf == "null":
                args = ["ffmpeg", "-i", str(source), "-filter:v", "setpts=PTS/" + str(speed), "-filter:a", f"atempo={max(0.5, min(2.0, speed))}"]
        if compress:
            args.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "28", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"])
        else:
            args.extend(["-c:a", "copy"])
        args.extend(["-y", str(output_path)])

        await asyncio.to_thread(run_command, args)
        return {
            "success": True,
            "input_path": str(source),
            "output_path": str(output_path),
            "mode": mode,
            "file_size": output_path.stat().st_size if output_path.exists() else None,
        }

    async def thumbnail(self, input_path: str, at_second: float = 1.0) -> dict[str, Any]:
        require_binary("ffmpeg")
        source = resolve_existing_file(input_path)
        target = settings.output_dir / "thumbnails" / f"{safe_filename(source.stem)}.jpg"
        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            run_command,
            ["ffmpeg", "-ss", str(at_second), "-i", str(source), "-frames:v", "1", "-q:v", "2", "-y", str(target)],
        )
        return {"success": True, "thumbnail_path": str(target)}
