# TrendReup Studio Pro

Desktop/web app for downloading social videos, crawling trends, managing reup ideas, batch queue, channels, content editing, video processing, SRT transcription, and subtitle translation.

The app is intentionally dependency-tolerant:

- Runs as a FastAPI local web app immediately.
- Opens as a PyWebView desktop window when `pywebview` is installed.
- Uses `yt-dlp` for download metadata and downloads.
- Uses Faster Whisper only when installed; otherwise the API returns a clear setup message.
- Uses FFmpeg for audio/subtitle media work when available.

## Quick Start

```powershell
python app.py --web
```

Open http://127.0.0.1:8765.

If your default `python` does not have dependencies, use the bundled Codex runtime:

```powershell
& "C:\Users\nt738\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" app.py --web
```

## Deploy To Vercel

This repository includes `vercel.json` and `api/index.py`, so Vercel can run the FastAPI app as a Python serverless function.

```powershell
vercel --prod
```

On Vercel, runtime data is written to the platform temp directory. That keeps the deploy read-only safe, but it also means downloaded files and SQLite data are ephemeral. For permanent production storage, set `STUDIO_DB`, `STUDIO_DOWNLOAD_DIR`, and `STUDIO_OUTPUT_DIR` to a mounted or external storage-backed path/provider.

## Local/VPS Worker

Use a worker on a Windows machine or VPS for heavy downloading, browser fallback, FFmpeg processing, subtitle/audio work, and cookie-backed platforms.

```powershell
python worker.py --api-url http://127.0.0.1:8765 --process-video --hide-caption-area --watermark @brand
```

For Douyin/Kwai/Likee browser fallback, install optional dependencies and enable Selenium:

```powershell
pip install -r requirements-optional.txt
$env:STUDIO_BROWSER_FALLBACK="1"
python worker.py --api-url http://127.0.0.1:8765 --process-video
```

The deployed Vercel dashboard can create automation plans and queue items, while the worker does the long-running download/edit jobs on a machine that has Chrome, FFmpeg, cookies, and durable storage.

## Optional Desktop Window

```powershell
pip install -r requirements-optional.txt
python app.py
```

If PyWebView is not installed, `app.py` falls back to opening the browser.

## Main Features

- Quick reup workflow: download, optional anti-detect processing, edited caption, and video history.
- Auto Studio workflow: paste a keyword/topic, select platforms, save candidates, and queue them for workers.
- Worker API for local/VPS machines to claim queue items, process media, and report results back to the dashboard.
- Download video or metadata from Auto/yt-dlp, YouTube, TikTok, Douyin, Rednote/Xiaohongshu, Instagram, Facebook, Kwai, Likee, and Twitter/X.
- Crawl profile/channel URLs through `yt-dlp` playlist extraction.
- Trend crawler for keywords and active content ideas with saved trend library.
- Content ideas manager for keyword/topic/idea/hashtag planning.
- Batch queue manager with priority and process-next workflow.
- Channel manager for destination identities.
- Content editor for cleaned captions and category hashtag packs.
- Video processor for anti-detect edits, mirroring, watermark, speed adjustment, and compression when FFmpeg is installed.
- Transcribe local videos into timestamped SRT when Faster Whisper and FFmpeg are available.
- Translate subtitles through LibreTranslate-compatible API when configured, with a built-in offline placeholder fallback.
- Render translated subtitles onto videos when FFmpeg is available.
- Track job history, videos, channels, queue, ideas, crawled content, settings, and edits in SQLite.

## Environment

Copy `.env.example` to `.env` if you want external translation:

```powershell
Copy-Item .env.example .env
```

## API

- `GET /api/health`
- `POST /api/download`
- `POST /api/reup`
- `POST /api/crawl`
- `POST /api/transcribe`
- `POST /api/dub`
- `GET /api/stats`
- `GET/POST /api/ideas`
- `POST /api/trends/search`
- `POST /api/trends/crawl-ideas`
- `GET /api/trends/content`
- `GET/POST /api/queue`
- `POST /api/queue/process-next`
- `GET/POST /api/channels`
- `POST /api/content/edit`
- `POST /api/video/process`
- `GET /api/jobs`
- `GET /api/platforms`

## Notes

Some platforms require cookies or login for certain URLs. Put Netscape-format cookie files in `cookies/` and select the matching platform in the UI.
