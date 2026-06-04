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
        hide_caption_area: bool = False,
        output_aspect: str = "source",
        mute_original: bool = False,
        background_music_path: str | None = None,
    ) -> dict[str, Any]:
        require_binary("ffmpeg")
        source = resolve_existing_file(input_path)
        target_dir = output_dir or settings.output_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / f"{safe_filename(source.stem)}_{mode}.mp4"

        filters: list[str] = []
        if mode == "anti_detect" or mirror:
            filters.append("hflip" if mirror else "eq=brightness=0.015:saturation=1.04")
        if output_aspect == "9:16":
            filters.append("scale=1080:-2,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2")
        elif output_aspect == "1:1":
            filters.append("scale=1080:-2,crop=1080:1080:(in_w-1080)/2:(in_h-1080)/2")
        if hide_caption_area:
            filters.append("drawbox=x=0:y=ih*0.72:w=iw:h=ih*0.18:color=black@0.62:t=fill")
        if watermark_text:
            escaped = watermark_text.replace(":", "\\:").replace("'", "\\'")
            filters.append(f"drawtext=text='{escaped}':x=20:y=h-th-24:fontcolor=white:fontsize=24:box=1:boxcolor=black@0.35")
        if speed and abs(speed - 1.0) > 0.001:
            filters.append(f"setpts=PTS/{speed}")
        vf = ",".join(filters) if filters else "null"

        music = Path(background_music_path).expanduser() if background_music_path else None
        has_music = bool(music and music.exists())
        args = ["ffmpeg", "-i", str(source)]
        if has_music:
            args.extend(["-stream_loop", "-1", "-i", str(music)])
        if has_music:
            video_chain = vf if vf != "null" else "null"
            if mute_original:
                graph = f"[0:v]{video_chain}[vout];[1:a]volume=0.18[aout]"
            else:
                audio_speed = f",atempo={max(0.5, min(2.0, speed))}" if speed and abs(speed - 1.0) > 0.001 else ""
                graph = f"[0:v]{video_chain}[vout];[0:a]volume=0.85{audio_speed}[a0];[1:a]volume=0.14[a1];[a0][a1]amix=inputs=2:duration=first[aout]"
            args.extend(["-filter_complex", graph, "-map", "[vout]", "-map", "[aout]", "-shortest"])
        else:
            args.extend(["-vf", vf])
            if speed and abs(speed - 1.0) > 0.001:
                args.extend(["-filter:a", f"atempo={max(0.5, min(2.0, speed))}"])
            if mute_original:
                args.extend(["-an"])
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
