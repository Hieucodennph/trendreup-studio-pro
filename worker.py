from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path
from typing import Any

import requests

from core.config import ensure_runtime_dirs, settings
from core.content_manager import ContentManager
from core.url_tools import detect_platform, extract_first_url
from core.video_processor import VideoProcessor
from downloaders import (
    DouyinDownloader,
    FacebookDownloader,
    GenericDownloader,
    InstagramDownloader,
    KwaiDownloader,
    LikeeDownloader,
    RednoteDownloader,
    TikTokDownloader,
    TwitterDownloader,
    YouTubeDownloader,
)


PLATFORMS = {
    "auto": GenericDownloader,
    "youtube": YouTubeDownloader,
    "tiktok": TikTokDownloader,
    "douyin": DouyinDownloader,
    "rednote": RednoteDownloader,
    "instagram": InstagramDownloader,
    "facebook": FacebookDownloader,
    "kwai": KwaiDownloader,
    "likee": LikeeDownloader,
    "twitter": TwitterDownloader,
}


def post(api_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(f"{api_url.rstrip('/')}{path}", json=payload, timeout=45)
    response.raise_for_status()
    return response.json()


def create_downloader(platform: str, url: str, quality: str):
    key = platform if platform != "auto" else detect_platform(url)
    cls = PLATFORMS.get(key, GenericDownloader)
    cookie_candidates = [
        settings.cookies_dir / f"{key}.txt",
        settings.cookies_dir / f"{key}_cookies.txt",
    ]
    cookie_path = next((path for path in cookie_candidates if path.exists()), cookie_candidates[0])
    return key, cls(cookie_path=str(cookie_path), quality=quality)


async def process_item(item: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    url = extract_first_url(item["url"])
    platform, downloader = create_downloader(item.get("platform") or "auto", url, args.quality)
    metadata = await downloader.fetch_metadata(url)
    video_path = await downloader.download(url, settings.download_dir / platform)

    output_path = str(video_path)
    if args.process_video:
        processed = await VideoProcessor().process(
            str(video_path),
            mode="auto_reup",
            output_dir=settings.output_dir,
            watermark_text=args.watermark,
            speed=args.speed,
            mirror=args.mirror,
            compress=True,
            hide_caption_area=args.hide_caption_area,
            output_aspect=args.output_aspect,
            mute_original=args.mute_original,
            background_music_path=args.background_music or None,
        )
        output_path = processed["output_path"]

    caption = ContentManager().auto_edit(metadata.description or metadata.title, args.caption_category)
    path_obj = Path(output_path)
    return {
        "success": True,
        "queue_id": item["id"],
        "platform": platform,
        "video_path": str(video_path),
        "output_path": output_path,
        "caption": caption,
        "events": downloader.events,
        "video": {
            "id": metadata.id or str(abs(hash(url))),
            "title": metadata.title,
            "source_url": url,
            "source_platform": platform,
            "output_path": output_path,
            "status": "processed" if args.process_video else "downloaded",
            "channel_id": item.get("channel_id") or "default",
            "views": metadata.view_count,
            "likes": metadata.like_count,
            "duration": metadata.duration,
            "file_size": path_obj.stat().st_size if path_obj.exists() else 0,
        },
    }


async def run_worker(args: argparse.Namespace) -> None:
    ensure_runtime_dirs()
    print(f"worker={args.worker_id} api={args.api_url} interval={args.interval}s")
    while True:
        try:
            claimed = post(args.api_url, "/api/worker/claim", {"worker_id": args.worker_id})
            item = claimed.get("item")
            if not item:
                time.sleep(args.interval)
                continue
            print(f"claimed queue_id={item['id']} platform={item.get('platform')} url={item['url'][:80]}")
            try:
                result = await process_item(item, args)
                post(args.api_url, "/api/worker/complete", {"worker_id": args.worker_id, "queue_id": item["id"], "result": result})
                print(f"completed queue_id={item['id']} output={result.get('output_path')}")
            except Exception as exc:
                post(args.api_url, "/api/worker/fail", {"worker_id": args.worker_id, "queue_id": item["id"], "error": str(exc)})
                print(f"failed queue_id={item['id']} error={exc}")
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"worker loop error: {exc}")
            time.sleep(args.interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="TrendReup local/VPS downloader worker")
    parser.add_argument("--api-url", default="http://127.0.0.1:8765")
    parser.add_argument("--worker-id", default="local-worker")
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--quality", default="1080p")
    parser.add_argument("--process-video", action="store_true")
    parser.add_argument("--watermark", default="")
    parser.add_argument("--speed", type=float, default=1.03)
    parser.add_argument("--mirror", action="store_true")
    parser.add_argument("--hide-caption-area", action="store_true")
    parser.add_argument("--output-aspect", default="source", choices=["source", "9:16", "1:1"])
    parser.add_argument("--mute-original", action="store_true")
    parser.add_argument("--background-music", default="")
    parser.add_argument("--caption-category", default="general")
    args = parser.parse_args()
    asyncio.run(run_worker(args))


if __name__ == "__main__":
    main()

