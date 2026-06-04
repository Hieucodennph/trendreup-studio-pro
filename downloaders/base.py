from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from core.contract import VideoMetadata
from core.utils import safe_filename


class YtDlpDownloader:
    platform = "generic"
    PLATFORM_CONFIG: dict[str, dict[str, Any]] = {
        "auto": {"format": "bv*+ba/best", "merge_output_format": "mp4"},
        "youtube": {"format": "bv*[height<=1080]+ba/best[height<=1080]/best", "format_sort": ["res:1080", "ext:mp4:m4a"]},
        "tiktok": {"format": "best", "headers": {"User-Agent": "TikTok 26.2.0 rv:262018 (iPhone; iOS 16.0; en_US) Cronet"}},
        "douyin": {"format": "best", "headers": {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"}},
        "rednote": {"format": "best"},
        "instagram": {"format": "bestvideo+bestaudio/best"},
        "facebook": {"format": "best"},
        "kwai": {"format": "best"},
        "likee": {"format": "best"},
        "twitter": {"format": "bestvideo+bestaudio/best"},
    }

    def __init__(
        self,
        cookie_path: str | None = None,
        quality: str = "1080p",
        audio_only: bool = False,
        write_subtitles: bool = False,
        write_thumbnail: bool = False,
    ):
        self.cookie_path = cookie_path
        self.quality = quality
        self.audio_only = audio_only
        self.write_subtitles = write_subtitles
        self.write_thumbnail = write_thumbnail
        self.events: list[str] = []

    def _options(self, output_dir: Path | None = None, download: bool = False) -> dict[str, Any]:
        config = self.PLATFORM_CONFIG.get(self.platform, self.PLATFORM_CONFIG["auto"])
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": False,
            "noplaylist": False,
            "extract_flat": False,
            "retries": 5,
            "fragment_retries": 5,
            "socket_timeout": 60,
            "concurrent_fragment_downloads": 4,
            "windowsfilenames": True,
            "trim_file_name": 160,
            "progress_hooks": [self._progress_hook],
        }
        if config.get("headers"):
            options["headers"] = config["headers"]
        if config.get("format_sort"):
            options["format_sort"] = config["format_sort"]
        if self.cookie_path and Path(self.cookie_path).exists():
            options["cookiefile"] = self.cookie_path
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            options["outtmpl"] = str(output_dir / "%(uploader|unknown)s - %(title).120s [%(id)s].%(ext)s")
            options["restrictfilenames"] = False
        if download:
            options["format"] = self._format_selector(config)
            options["merge_output_format"] = config.get("merge_output_format", "mp4")
            options["writethumbnail"] = self.write_thumbnail
            options["writesubtitles"] = self.write_subtitles
            options["writeautomaticsub"] = self.write_subtitles
            options["subtitleslangs"] = ["vi", "en", "zh-Hans", "zh-Hant"]
            if self.audio_only:
                options["format"] = "bestaudio/best"
                options["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
        else:
            options["skip_download"] = True
        return options

    def _format_selector(self, config: dict[str, Any]) -> str:
        if self.quality == "best":
            return config.get("format", "bv*+ba/best")
        if self.quality == "720p":
            return "bv*[height<=720]+ba/best[height<=720]/best"
        if self.quality == "480p":
            return "bv*[height<=480]+ba/best[height<=480]/best"
        return config.get("format", "bv*[height<=1080]+ba/best[height<=1080]/best")

    def _progress_hook(self, data: dict[str, Any]) -> None:
        status = data.get("status")
        if status == "downloading":
            percent = data.get("_percent_str", "").strip()
            speed = data.get("_speed_str", "").strip()
            eta = data.get("_eta_str", "").strip()
            message = " ".join(part for part in [percent, speed, f"ETA {eta}" if eta else ""] if part)
            if message and (not self.events or self.events[-1] != message):
                self.events.append(message)
                self.events = self.events[-20:]
        elif status == "finished":
            filename = data.get("filename")
            self.events.append(f"finished {filename}" if filename else "finished")

    async def _extract(self, url: str, download: bool = False, output_dir: Path | None = None) -> dict[str, Any]:
        try:
            import yt_dlp
        except ImportError as exc:
            raise RuntimeError("yt-dlp is not installed. Run: pip install yt-dlp") from exc

        def work() -> dict[str, Any]:
            with yt_dlp.YoutubeDL(self._options(output_dir=output_dir, download=download)) as ydl:
                return ydl.extract_info(url, download=download)

        return await asyncio.to_thread(work)

    def _metadata_from_info(self, info: dict[str, Any]) -> VideoMetadata:
        return VideoMetadata(
            id=str(info.get("id") or ""),
            title=info.get("title") or "Untitled video",
            url=info.get("webpage_url") or info.get("original_url") or "",
            platform=self.platform,
            author=info.get("uploader") or info.get("channel") or info.get("creator") or "",
            duration=info.get("duration"),
            thumbnail=info.get("thumbnail") or "",
            description=info.get("description") or "",
            upload_date=info.get("upload_date") or "",
            view_count=info.get("view_count"),
            like_count=info.get("like_count"),
            raw=info,
        )

    async def fetch_metadata(self, url: str) -> VideoMetadata:
        info = await self._extract(url, download=False)
        if "entries" in info and info["entries"]:
            first = next((entry for entry in info["entries"] if entry), None)
            if first:
                info = first
        return self._metadata_from_info(info)

    async def download(self, url: str, output_dir: Path) -> Path:
        before = set(output_dir.glob("*")) if output_dir.exists() else set()
        info = await self._extract(url, download=True, output_dir=output_dir)
        after = set(output_dir.glob("*"))
        new_files = sorted(after - before, key=lambda p: p.stat().st_mtime, reverse=True)
        if new_files:
            return new_files[0]

        requested = info.get("requested_downloads") or []
        if requested and requested[0].get("filepath"):
            return Path(requested[0]["filepath"])

        title = safe_filename(info.get("title") or info.get("id") or "download")
        matches = sorted(output_dir.glob(f"*{title}*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return matches[0]
        raise RuntimeError("Download completed, but the output file could not be located.")

    async def crawl_profile(self, url: str, limit: int = 20) -> list[VideoMetadata]:
        info = await self._extract(url, download=False)
        entries = info.get("entries") or []
        videos: list[VideoMetadata] = []
        for entry in entries:
            if not entry:
                continue
            videos.append(self._metadata_from_info(entry))
            if len(videos) >= limit:
                break
        if not videos and info:
            videos.append(self._metadata_from_info(info))
        return videos
