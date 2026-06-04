from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


class JobStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    platform TEXT,
                    input TEXT,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    source_url TEXT NOT NULL,
                    source_platform TEXT,
                    output_path TEXT,
                    thumbnail_path TEXT,
                    status TEXT DEFAULT 'pending',
                    views INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    channel_id TEXT,
                    keyword_idea_id INTEGER,
                    duration REAL DEFAULT 0,
                    file_size REAL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    processed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    channel_id TEXT,
                    platform TEXT,
                    priority INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    scheduled_at TEXT
                );

                CREATE TABLE IF NOT EXISTS channels (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    platform TEXT DEFAULT 'youtube',
                    api_key TEXT,
                    cookies TEXT,
                    status TEXT DEFAULT 'active',
                    total_videos INTEGER DEFAULT 0,
                    total_views INTEGER DEFAULT 0,
                    total_likes INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_used TEXT
                );

                CREATE TABLE IF NOT EXISTS content_ideas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT CHECK(type IN ('keyword', 'topic', 'idea', 'hashtag')),
                    category TEXT,
                    platform_filter TEXT,
                    is_active INTEGER DEFAULT 1,
                    priority INTEGER DEFAULT 0,
                    last_scraped TEXT,
                    total_results INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS crawled_content (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    description TEXT,
                    video_url TEXT NOT NULL,
                    thumbnail_url TEXT,
                    source_platform TEXT,
                    author TEXT,
                    view_count INTEGER DEFAULT 0,
                    like_count INTEGER DEFAULT 0,
                    comment_count INTEGER DEFAULT 0,
                    share_count INTEGER DEFAULT 0,
                    duration REAL DEFAULT 0,
                    trend_score REAL DEFAULT 0,
                    idea_id INTEGER,
                    is_downloaded INTEGER DEFAULT 0,
                    is_processed INTEGER DEFAULT 0,
                    crawled_at TEXT NOT NULL,
                    downloaded_at TEXT,
                    FOREIGN KEY (idea_id) REFERENCES content_ideas(id)
                );

                CREATE TABLE IF NOT EXISTS edit_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT,
                    original_content TEXT,
                    edited_content TEXT,
                    edit_type TEXT CHECK(edit_type IN ('auto', 'manual')),
                    changes_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (video_id) REFERENCES videos(id)
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS worker_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id TEXT NOT NULL,
                    queue_id INTEGER,
                    status TEXT NOT NULL,
                    detail_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
                CREATE INDEX IF NOT EXISTS idx_queue_status ON queue(status);
                CREATE INDEX IF NOT EXISTS idx_crawled_idea ON crawled_content(idea_id);
                CREATE INDEX IF NOT EXISTS idx_ideas_active ON content_ideas(is_active);
                """
            )
            count = conn.execute("SELECT COUNT(*) FROM content_ideas").fetchone()[0]
            if count == 0:
                self._insert_sample_ideas(conn)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _insert_sample_ideas(self, conn: sqlite3.Connection) -> None:
        sample_ideas = [
            ("tri tue nhan tao", "keyword", "technology", "all", 10),
            ("cach lam giau", "keyword", "finance", "all", 9),
            ("review dien thoai", "topic", "technology", "youtube", 8),
            ("du lich bui", "idea", "travel", "tiktok", 7),
            ("am thuc duong pho", "topic", "food", "tiktok,douyin", 8),
            ("hoc tieng anh online", "keyword", "education", "youtube", 7),
            ("startup cong nghe", "idea", "business", "all", 6),
            ("cham soc da", "topic", "beauty", "tiktok", 7),
            ("#xuhuong", "hashtag", "trending", "tiktok", 9),
            ("#fyp", "hashtag", "trending", "tiktok", 10),
        ]
        now = self._now()
        conn.executemany(
            """
            INSERT INTO content_ideas
            (name, type, category, platform_filter, priority, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            [(name, kind, category, platform, priority, now, now) for name, kind, category, platform, priority in sample_ideas],
        )

    def create(self, kind: str, input_value: str, platform: str | None = None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO jobs (kind, status, platform, input, result_json, error, created_at, updated_at)
                VALUES (?, 'running', ?, ?, '{}', NULL, ?, ?)
                """,
                (kind, platform, input_value, now, now),
            )
            return int(cursor.lastrowid)

    def complete(self, job_id: int, result: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                "UPDATE jobs SET status='success', result_json=?, error=NULL, updated_at=? WHERE id=?",
                (json.dumps(result, ensure_ascii=False), now, job_id),
            )

    def fail(self, job_id: int, error: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                "UPDATE jobs SET status='failed', error=?, updated_at=? WHERE id=?",
                (error, now, job_id),
            )

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["result"] = json.loads(item.pop("result_json") or "{}")
            result.append(item)
        return result

    def add_video(self, data: dict[str, Any]) -> None:
        now = self._now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO videos
                (id, title, source_url, source_platform, output_path, thumbnail_path, status,
                 views, likes, shares, comments, channel_id, keyword_idea_id, duration, file_size,
                 created_at, processed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM videos WHERE id=?), ?), ?)
                """,
                (
                    data["id"],
                    data.get("title", ""),
                    data["source_url"],
                    data.get("source_platform", ""),
                    data.get("output_path", ""),
                    data.get("thumbnail_path", ""),
                    data.get("status", "completed"),
                    data.get("views", 0) or 0,
                    data.get("likes", 0) or 0,
                    data.get("shares", 0) or 0,
                    data.get("comments", 0) or 0,
                    data.get("channel_id", ""),
                    data.get("keyword_idea_id"),
                    data.get("duration", 0) or 0,
                    data.get("file_size", 0) or 0,
                    data["id"],
                    now,
                    data.get("processed_at", now),
                ),
            )

    def list_videos(self, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM videos WHERE status=? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM videos ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def add_to_queue(self, url: str, channel_id: str = "default", platform: str = "auto", priority: int = 0) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO queue (url, channel_id, platform, priority, status, retry_count, created_at)
                VALUES (?, ?, ?, ?, 'pending', 0, ?)
                """,
                (url, channel_id, platform, priority, self._now()),
            )
            return int(cursor.lastrowid)

    def list_queue(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM queue WHERE status=? ORDER BY priority DESC, created_at ASC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM queue ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'processing' THEN 1 ELSE 2 END, priority DESC, created_at ASC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def update_queue_status(self, queue_id: int, status: str, error_message: str | None = None) -> None:
        with self.connect() as conn:
            if error_message:
                conn.execute(
                    "UPDATE queue SET status=?, error_message=?, retry_count=retry_count+1 WHERE id=?",
                    (status, error_message, queue_id),
                )
            else:
                conn.execute("UPDATE queue SET status=?, error_message=NULL WHERE id=?", (status, queue_id))

    def claim_next_queue_item(self, worker_id: str) -> dict[str, Any] | None:
        now = self._now()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM queue
                WHERE status='pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            queue_id = int(row["id"])
            conn.execute("UPDATE queue SET status='processing', error_message=NULL WHERE id=?", (queue_id,))
            conn.execute(
                """
                INSERT INTO worker_runs (worker_id, queue_id, status, detail_json, created_at, updated_at)
                VALUES (?, ?, 'processing', '{}', ?, ?)
                """,
                (worker_id, queue_id, now, now),
            )
            return dict(row)

    def complete_queue_item(self, queue_id: int, worker_id: str, result: dict[str, Any]) -> None:
        now = self._now()
        with self.connect() as conn:
            conn.execute("UPDATE queue SET status='completed', error_message=NULL WHERE id=?", (queue_id,))
            conn.execute(
                """
                INSERT INTO worker_runs (worker_id, queue_id, status, detail_json, created_at, updated_at)
                VALUES (?, ?, 'completed', ?, ?, ?)
                """,
                (worker_id, queue_id, json.dumps(result, ensure_ascii=False), now, now),
            )

    def fail_queue_item(self, queue_id: int, worker_id: str, error_message: str) -> None:
        now = self._now()
        with self.connect() as conn:
            conn.execute(
                "UPDATE queue SET status='failed', error_message=?, retry_count=retry_count+1 WHERE id=?",
                (error_message, queue_id),
            )
            conn.execute(
                """
                INSERT INTO worker_runs (worker_id, queue_id, status, detail_json, created_at, updated_at)
                VALUES (?, ?, 'failed', ?, ?, ?)
                """,
                (worker_id, queue_id, json.dumps({"error": error_message}, ensure_ascii=False), now, now),
            )

    def list_worker_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM worker_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["detail"] = json.loads(item.pop("detail_json") or "{}")
            result.append(item)
        return result

    def add_channel(self, channel_id: str, name: str, platform: str = "youtube", api_key: str = "", cookies: str = "") -> None:
        now = self._now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO channels (id, name, platform, api_key, cookies, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    platform=excluded.platform,
                    api_key=excluded.api_key,
                    cookies=excluded.cookies,
                    status='active'
                """,
                (channel_id, name, platform, api_key, cookies, now),
            )

    def list_channels(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM channels WHERE status='active' ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def delete_channel(self, channel_id: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE channels SET status='deleted' WHERE id=?", (channel_id,))

    def add_idea(self, name: str, idea_type: str, category: str = "general", platform_filter: str = "all", priority: int = 0) -> int:
        now = self._now()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO content_ideas (name, type, category, platform_filter, priority, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (name, idea_type, category, platform_filter, priority, now, now),
            )
            return int(cursor.lastrowid)

    def list_ideas(self, idea_type: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if idea_type and idea_type != "all":
                rows = conn.execute(
                    "SELECT * FROM content_ideas WHERE is_active=1 AND type=? ORDER BY priority DESC, created_at ASC",
                    (idea_type,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM content_ideas WHERE is_active=1 ORDER BY priority DESC, created_at ASC"
                ).fetchall()
        return [dict(row) for row in rows]

    def delete_idea(self, idea_id: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE content_ideas SET is_active=0, updated_at=? WHERE id=?", (self._now(), idea_id))

    def update_idea_last_scraped(self, idea_id: int, total_results: int) -> None:
        now = self._now()
        with self.connect() as conn:
            conn.execute(
                "UPDATE content_ideas SET last_scraped=?, total_results=?, updated_at=? WHERE id=?",
                (now, total_results, now, idea_id),
            )

    def save_crawled_content(self, video_data: dict[str, Any]) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO crawled_content
                (title, description, video_url, thumbnail_url, source_platform, author,
                 view_count, like_count, comment_count, share_count, duration, trend_score, idea_id, crawled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_data.get("title", ""),
                    video_data.get("description", ""),
                    video_data.get("video_url", ""),
                    video_data.get("thumbnail_url", ""),
                    video_data.get("source_platform", ""),
                    video_data.get("author", ""),
                    video_data.get("view_count", 0) or 0,
                    video_data.get("like_count", 0) or 0,
                    video_data.get("comment_count", 0) or 0,
                    video_data.get("share_count", 0) or 0,
                    video_data.get("duration", 0) or 0,
                    video_data.get("trend_score", 0) or 0,
                    video_data.get("idea_id"),
                    self._now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_crawled_content(self, limit: int = 100, is_downloaded: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if is_downloaded is None:
                rows = conn.execute(
                    """
                    SELECT c.*, i.name AS idea_name
                    FROM crawled_content c
                    LEFT JOIN content_ideas i ON c.idea_id=i.id
                    ORDER BY c.trend_score DESC, c.crawled_at DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT c.*, i.name AS idea_name
                    FROM crawled_content c
                    LEFT JOIN content_ideas i ON c.idea_id=i.id
                    WHERE c.is_downloaded=?
                    ORDER BY c.trend_score DESC, c.crawled_at DESC LIMIT ?
                    """,
                    (is_downloaded, limit),
                ).fetchall()
        return [dict(row) for row in rows]

    def save_edit(self, original: str, edited: str, edit_type: str = "auto", video_id: str | None = None) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO edit_history (video_id, original_content, edited_content, edit_type, changes_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (video_id, original, edited, edit_type, "{}", self._now()),
            )
            return int(cursor.lastrowid)

    def upsert_setting(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value, self._now()),
            )

    def list_settings(self) -> dict[str, str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def dashboard_stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            scalar = lambda sql: conn.execute(sql).fetchone()[0]
            return {
                "videos": scalar("SELECT COUNT(*) FROM videos"),
                "queue_pending": scalar("SELECT COUNT(*) FROM queue WHERE status='pending'"),
                "queue_failed": scalar("SELECT COUNT(*) FROM queue WHERE status='failed'"),
                "channels": scalar("SELECT COUNT(*) FROM channels WHERE status='active'"),
                "ideas": scalar("SELECT COUNT(*) FROM content_ideas WHERE is_active=1"),
                "crawled": scalar("SELECT COUNT(*) FROM crawled_content"),
                "downloaded": scalar("SELECT COUNT(*) FROM crawled_content WHERE is_downloaded=1"),
                "processed": scalar("SELECT COUNT(*) FROM crawled_content WHERE is_processed=1"),
                "workers": scalar("SELECT COUNT(*) FROM worker_runs"),
                "total_views": scalar("SELECT COALESCE(SUM(views), 0) FROM videos"),
                "total_likes": scalar("SELECT COALESCE(SUM(likes), 0) FROM videos"),
            }
