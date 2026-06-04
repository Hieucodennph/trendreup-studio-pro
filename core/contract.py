from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class VideoMetadata:
    id: str
    title: str
    url: str
    platform: str
    author: str = ""
    duration: float | None = None
    thumbnail: str = ""
    description: str = ""
    upload_date: str = ""
    view_count: int | None = None
    like_count: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("raw", None)
        return data


class Downloader(Protocol):
    platform: str

    async def fetch_metadata(self, url: str) -> VideoMetadata:
        ...

    async def download(self, url: str, output_dir: Path) -> Path:
        ...

    async def crawl_profile(self, url: str, limit: int = 20) -> list[VideoMetadata]:
        ...
