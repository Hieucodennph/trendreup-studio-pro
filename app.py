from __future__ import annotations

import argparse
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.config import ensure_runtime_dirs, settings
from core.content_manager import ContentManager
from core.database import JobStore
from core.trend_crawler import TrendCrawler
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
from dub.pipeline import DubPipeline
from dub.transcriber import Transcriber

ensure_runtime_dirs()

app = FastAPI(title="Studio Downloader API", version="1.0.0")
job_store = JobStore(settings.database_path)
trend_crawler = TrendCrawler()
content_manager = ContentManager()
video_processor = VideoProcessor()
ui_path = Path(__file__).parent / "ui" / "static"
app.mount("/static", StaticFiles(directory=str(ui_path)), name="static")


class DownloadRequest(BaseModel):
    url: str
    platform: str = "auto"
    download_video: bool = True
    output_dir: str | None = None
    quality: str = "1080p"
    audio_only: bool = False
    write_subtitles: bool = False
    write_thumbnail: bool = False


class CrawlRequest(BaseModel):
    profile_url: str
    platform: str
    limit: int = Field(default=20, ge=1, le=200)


class TranscribeRequest(BaseModel):
    video_path: str
    source_lang: str = "auto"


class DubRequest(BaseModel):
    video_path: str
    source_lang: str = "auto"
    target_lang: str = "vi"
    burn_subtitles: bool = False


class QuickReupRequest(BaseModel):
    url: str
    platform: str = "auto"
    channel_id: str = "default"
    process_video: bool = False
    watermark_text: str = ""
    auto_caption: bool = True
    quality: str = "1080p"


class IdeaRequest(BaseModel):
    name: str
    type: str = "keyword"
    category: str = "general"
    platform_filter: str = "all"
    priority: int = Field(default=0, ge=0, le=10)


class TrendSearchRequest(BaseModel):
    keyword: str
    platforms: list[str] = Field(default_factory=lambda: ["youtube", "tiktok", "douyin"])
    max_results: int = Field(default=5, ge=1, le=25)
    save: bool = True


class CrawlIdeasRequest(BaseModel):
    platforms: list[str] | None = None
    max_per_idea: int = Field(default=3, ge=1, le=20)


class AutoReupPlanRequest(BaseModel):
    keyword: str
    platforms: list[str] = Field(default_factory=lambda: ["youtube", "tiktok", "douyin"])
    max_results_per_platform: int = Field(default=5, ge=1, le=25)
    channel_id: str = "default"
    priority: int = Field(default=5, ge=0, le=10)
    auto_queue: bool = True
    min_trend_score: float = Field(default=0, ge=0, le=100)


class QueueRequest(BaseModel):
    url: str
    channel_id: str = "default"
    platform: str = "auto"
    priority: int = Field(default=0, ge=0, le=10)


class ChannelRequest(BaseModel):
    id: str
    name: str
    platform: str = "youtube"
    api_key: str = ""
    cookies: str = ""


class ContentEditRequest(BaseModel):
    text: str
    category: str = "general"
    video_id: str | None = None


class ProcessVideoRequest(BaseModel):
    input_path: str
    mode: str = "anti_detect"
    watermark_text: str = ""
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    mirror: bool = False
    compress: bool = True
    hide_caption_area: bool = False
    output_aspect: str = "source"
    mute_original: bool = False
    background_music_path: str = ""


class WorkerClaimRequest(BaseModel):
    worker_id: str = "local-worker"


class WorkerCompleteRequest(BaseModel):
    worker_id: str = "local-worker"
    queue_id: int
    result: dict[str, Any] = Field(default_factory=dict)


class WorkerFailRequest(BaseModel):
    worker_id: str = "local-worker"
    queue_id: int
    error: str


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


def create_downloader(platform: str, url: str = "", **options: Any):
    key = platform.lower().strip()
    if key == "auto" and url:
        key = detect_platform(url)
    cls = PLATFORMS.get(key)
    if not cls:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")
    cookie_path = settings.cookies_dir / f"{key}.txt"
    return cls(cookie_path=str(cookie_path), **options)


async def tracked(kind: str, input_value: str, platform: str | None, work):
    job_id = job_store.create(kind, input_value, platform)
    try:
        result = await work()
        result["job_id"] = job_id
        job_store.complete(job_id, result)
        return result
    except Exception as exc:
        job_store.fail(job_id, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "message": "TrendReup Studio Pro is running",
        "app": "TrendReup Studio Pro",
        "platforms": list(PLATFORMS),
        "output_dir": str(settings.output_dir),
        "download_dir": str(settings.download_dir),
        "runtime_root": str(settings.runtime_root),
        "stats": job_store.dashboard_stats(),
    }


@app.get("/api/platforms")
async def platforms() -> dict[str, Any]:
    return {"platforms": [{"id": key, "label": key.title()} for key in PLATFORMS]}


@app.get("/api/jobs")
async def jobs(limit: int = 50) -> dict[str, Any]:
    return {"jobs": job_store.list_recent(limit)}


@app.post("/api/download")
async def download_video(request: DownloadRequest) -> dict[str, Any]:
    async def work() -> dict[str, Any]:
        clean_url = extract_first_url(request.url)
        platform = detect_platform(clean_url) if request.platform == "auto" else request.platform
        downloader = create_downloader(
            platform,
            clean_url,
            quality=request.quality,
            audio_only=request.audio_only,
            write_subtitles=request.write_subtitles,
            write_thumbnail=request.write_thumbnail,
        )
        metadata = await downloader.fetch_metadata(clean_url)
        result: dict[str, Any] = {"success": True, "metadata": metadata.to_dict()}
        if request.download_video:
            output_dir = Path(request.output_dir).expanduser() if request.output_dir else settings.download_dir
            video_path = await downloader.download(clean_url, output_dir / platform)
            result["video_path"] = str(video_path)
            result["file_size"] = video_path.stat().st_size if video_path.exists() else None
            result["platform"] = platform
            result["events"] = downloader.events
            job_store.add_video(
                {
                    "id": metadata.id or str(hash(request.url)),
                    "title": metadata.title,
                    "source_url": clean_url,
                    "source_platform": platform,
                    "output_path": str(video_path),
                    "status": "downloaded",
                    "views": metadata.view_count,
                    "likes": metadata.like_count,
                    "duration": metadata.duration,
                    "file_size": result["file_size"] or 0,
                }
            )
        return result

    return await tracked("download", request.url, request.platform, work)


@app.post("/api/crawl")
async def crawl_profile(request: CrawlRequest) -> dict[str, Any]:
    async def work() -> dict[str, Any]:
        downloader = create_downloader(request.platform)
        videos = await downloader.crawl_profile(request.profile_url, request.limit)
        return {
            "success": True,
            "platform": request.platform,
            "count": len(videos),
            "videos": [video.to_dict() for video in videos],
        }

    return await tracked("crawl", request.profile_url, request.platform, work)


@app.post("/api/reup")
async def quick_reup(request: QuickReupRequest) -> dict[str, Any]:
    async def work() -> dict[str, Any]:
        clean_url = extract_first_url(request.url)
        platform = detect_platform(clean_url) if request.platform == "auto" else request.platform
        downloader = create_downloader(platform, clean_url, quality=request.quality)
        output_dir = settings.download_dir / platform
        metadata = await downloader.fetch_metadata(clean_url)
        video_path = await downloader.download(clean_url, output_dir)
        processed_path = None
        if request.process_video:
            processed = await video_processor.process(
                str(video_path),
                mode="anti_detect",
                output_dir=settings.output_dir,
                watermark_text=request.watermark_text,
                mirror=True,
                compress=True,
            )
            processed_path = processed["output_path"]
        caption = None
        if request.auto_caption:
            caption = content_manager.auto_edit(metadata.description or metadata.title, "general")
            job_store.save_edit(caption["original"], caption["edited"], "auto", metadata.id)
        job_store.add_video(
            {
                "id": metadata.id or str(hash(request.url)),
                "title": metadata.title,
                "source_url": clean_url,
                "source_platform": platform,
                "output_path": processed_path or str(video_path),
                "status": "processed" if processed_path else "downloaded",
                "channel_id": request.channel_id,
                "views": metadata.view_count,
                "likes": metadata.like_count,
                "duration": metadata.duration,
                "file_size": Path(processed_path or video_path).stat().st_size if Path(processed_path or video_path).exists() else 0,
            }
        )
        return {
            "success": True,
            "metadata": metadata.to_dict(),
            "platform": platform,
            "video_path": str(video_path),
            "processed_path": processed_path,
            "caption": caption,
            "events": downloader.events,
        }

    return await tracked("reup", request.url, request.platform, work)


@app.post("/api/transcribe")
async def transcribe_video(request: TranscribeRequest) -> dict[str, Any]:
    async def work() -> dict[str, Any]:
        transcriber = Transcriber()
        segments = await transcriber.transcribe_async(request.video_path, request.source_lang)
        output_dir = settings.output_dir / "transcribed"
        srt_path = output_dir / f"{Path(request.video_path).stem}.srt"
        transcriber.to_srt(segments, str(srt_path))
        return {
            "success": True,
            "segments": segments,
            "srt_path": str(srt_path),
            "segment_count": len(segments),
        }

    return await tracked("transcribe", request.video_path, None, work)


@app.post("/api/dub")
async def dub_video(request: DubRequest) -> dict[str, Any]:
    async def work() -> dict[str, Any]:
        pipeline = DubPipeline(settings.output_dir)
        return await pipeline.process(
            request.video_path,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            burn_subtitles=request.burn_subtitles,
        )

    return await tracked("dub", request.video_path, None, work)


@app.get("/api/videos")
async def videos(limit: int = 100, status: str | None = None) -> dict[str, Any]:
    return {"videos": job_store.list_videos(limit, status)}


@app.get("/api/stats")
async def stats() -> dict[str, Any]:
    return {"stats": job_store.dashboard_stats()}


@app.get("/api/ideas")
async def ideas(type: str | None = None) -> dict[str, Any]:
    return {"ideas": job_store.list_ideas(type)}


@app.post("/api/ideas")
async def add_idea(request: IdeaRequest) -> dict[str, Any]:
    idea_id = job_store.add_idea(request.name, request.type, request.category, request.platform_filter, request.priority)
    return {"success": True, "idea_id": idea_id, "ideas": job_store.list_ideas()}


@app.delete("/api/ideas/{idea_id}")
async def delete_idea(idea_id: int) -> dict[str, Any]:
    job_store.delete_idea(idea_id)
    return {"success": True}


@app.post("/api/trends/search")
async def trend_search(request: TrendSearchRequest) -> dict[str, Any]:
    results = trend_crawler.search(request.keyword, request.platforms, request.max_results)
    if request.save:
        for result in results:
            result["content_id"] = job_store.save_crawled_content(result)
    return {"success": True, "count": len(results), "results": results}


@app.post("/api/trends/crawl-ideas")
async def crawl_ideas(request: CrawlIdeasRequest) -> dict[str, Any]:
    active_ideas = job_store.list_ideas()
    results = trend_crawler.crawl_ideas(active_ideas, request.platforms, request.max_per_idea)
    counts: dict[int, int] = {}
    for result in results:
        result["content_id"] = job_store.save_crawled_content(result)
        idea_id = result.get("idea_id")
        if idea_id:
            counts[idea_id] = counts.get(idea_id, 0) + 1
    for idea_id, count in counts.items():
        job_store.update_idea_last_scraped(idea_id, count)
    return {"success": True, "ideas": len(active_ideas), "count": len(results), "results": results}


@app.post("/api/automation/plan")
async def auto_reup_plan(request: AutoReupPlanRequest) -> dict[str, Any]:
    results = trend_crawler.search(request.keyword, request.platforms, request.max_results_per_platform)
    selected = [item for item in results if float(item.get("trend_score") or 0) >= request.min_trend_score]
    saved = []
    queued = []
    for item in selected:
        content_id = job_store.save_crawled_content(item)
        item["content_id"] = content_id
        saved.append(item)
        if request.auto_queue:
            queue_id = job_store.add_to_queue(
                item["video_url"],
                request.channel_id,
                item.get("source_platform") or "auto",
                request.priority,
            )
            queued.append({"queue_id": queue_id, "url": item["video_url"], "platform": item.get("source_platform")})
    return {
        "success": True,
        "keyword": request.keyword,
        "platforms": request.platforms,
        "saved_count": len(saved),
        "queued_count": len(queued),
        "saved": saved,
        "queued": queued,
    }


@app.get("/api/trends/content")
async def crawled_content(limit: int = 100) -> dict[str, Any]:
    return {"content": job_store.list_crawled_content(limit)}


@app.get("/api/trends/hashtags")
async def trending_hashtags() -> dict[str, Any]:
    return {"hashtags": trend_crawler.hashtags()}


@app.get("/api/queue")
async def queue(status: str | None = None, limit: int = 100) -> dict[str, Any]:
    return {"queue": job_store.list_queue(status, limit)}


@app.post("/api/queue")
async def add_queue(request: QueueRequest) -> dict[str, Any]:
    queue_id = job_store.add_to_queue(request.url, request.channel_id, request.platform, request.priority)
    return {"success": True, "queue_id": queue_id, "queue": job_store.list_queue()}


@app.post("/api/queue/process-next")
async def process_next_queue() -> dict[str, Any]:
    pending = job_store.list_queue("pending", 1)
    if not pending:
        return {"success": True, "message": "Queue is empty", "processed": None}
    item = pending[0]
    job_store.update_queue_status(item["id"], "processing")
    try:
        result = await quick_reup(
            QuickReupRequest(
                url=item["url"],
                platform=item["platform"] or "auto",
                channel_id=item["channel_id"] or "default",
                process_video=False,
            )
        )
        job_store.update_queue_status(item["id"], "completed")
        return {"success": True, "processed": item, "result": result}
    except Exception as exc:
        job_store.update_queue_status(item["id"], "failed", str(exc))
        raise


@app.post("/api/worker/claim")
async def worker_claim(request: WorkerClaimRequest) -> dict[str, Any]:
    item = job_store.claim_next_queue_item(request.worker_id)
    return {"success": True, "item": item}


@app.post("/api/worker/complete")
async def worker_complete(request: WorkerCompleteRequest) -> dict[str, Any]:
    job_store.complete_queue_item(request.queue_id, request.worker_id, request.result)
    if request.result.get("video"):
        job_store.add_video(request.result["video"])
    return {"success": True}


@app.post("/api/worker/fail")
async def worker_fail(request: WorkerFailRequest) -> dict[str, Any]:
    job_store.fail_queue_item(request.queue_id, request.worker_id, request.error)
    return {"success": True}


@app.get("/api/worker/runs")
async def worker_runs(limit: int = 50) -> dict[str, Any]:
    return {"runs": job_store.list_worker_runs(limit)}


@app.get("/api/channels")
async def channels() -> dict[str, Any]:
    return {"channels": job_store.list_channels()}


@app.post("/api/channels")
async def add_channel(request: ChannelRequest) -> dict[str, Any]:
    job_store.add_channel(request.id, request.name, request.platform, request.api_key, request.cookies)
    return {"success": True, "channels": job_store.list_channels()}


@app.delete("/api/channels/{channel_id}")
async def delete_channel(channel_id: str) -> dict[str, Any]:
    job_store.delete_channel(channel_id)
    return {"success": True}


@app.post("/api/content/edit")
async def edit_content(request: ContentEditRequest) -> dict[str, Any]:
    result = content_manager.auto_edit(request.text, request.category)
    result["edit_id"] = job_store.save_edit(request.text, result["edited"], "auto", request.video_id)
    result["success"] = True
    return result


@app.post("/api/video/process")
async def process_video(request: ProcessVideoRequest) -> dict[str, Any]:
    async def work() -> dict[str, Any]:
        return await video_processor.process(
            request.input_path,
            mode=request.mode,
            output_dir=settings.output_dir,
            watermark_text=request.watermark_text,
            speed=request.speed,
            mirror=request.mirror,
            compress=request.compress,
            hide_caption_area=request.hide_caption_area,
            output_aspect=request.output_aspect,
            mute_original=request.mute_original,
            background_music_path=request.background_music_path or None,
        )

    return await tracked("process_video", request.input_path, None, work)


@app.get("/api/settings")
async def list_settings() -> dict[str, Any]:
    return {
        "settings": job_store.list_settings(),
        "runtime": {
            "runtime_root": str(settings.runtime_root),
            "download_dir": str(settings.download_dir),
            "output_dir": str(settings.output_dir),
            "database_path": str(settings.database_path),
            "cookies_dir": str(settings.cookies_dir),
        },
    }


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(ui_path / "index.html"))


def run_server(host: str, port: int) -> None:
    uvicorn.run(app, host=host, port=port, log_level="info")


def run_desktop(host: str, port: int) -> None:
    url = f"http://{host}:{port}"
    thread = threading.Thread(target=run_server, args=(host, port), daemon=True)
    thread.start()
    time.sleep(1)
    try:
        import webview
    except ImportError:
        webbrowser.open(url)
        thread.join()
        return

    webview.create_window("Studio Downloader", url, width=1280, height=820, min_size=(1024, 640))
    webview.start(debug=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Studio Downloader")
    parser.add_argument("--web", action="store_true", help="Run as a local web app instead of desktop window")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", default=settings.port, type=int)
    args = parser.parse_args()
    if args.web:
        run_server(args.host, args.port)
    else:
        run_desktop(args.host, args.port)


if __name__ == "__main__":
    main()
