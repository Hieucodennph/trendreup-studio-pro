from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


def _is_serverless() -> bool:
    return os.getenv("VERCEL") == "1" or os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None


def _default_runtime_root() -> Path:
    if _is_serverless():
        default_root = Path(tempfile.gettempdir()) / "trendreup-studio"
        return Path(os.getenv("STUDIO_RUNTIME_ROOT", str(default_root))).expanduser().resolve()
    return Path(os.getenv("STUDIO_RUNTIME_ROOT", ".")).expanduser().resolve()


def _path_from_env(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).expanduser().resolve()


_runtime_root = _default_runtime_root()


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("STUDIO_HOST", "127.0.0.1")
    port: int = int(os.getenv("STUDIO_PORT", "8765"))
    runtime_root: Path = _runtime_root
    output_dir: Path = _path_from_env("STUDIO_OUTPUT_DIR", str(_runtime_root / "output"))
    download_dir: Path = _path_from_env("STUDIO_DOWNLOAD_DIR", str(_runtime_root / "downloads"))
    database_path: Path = _path_from_env("STUDIO_DB", str(_runtime_root / "studio_downloader.db"))
    raw_dir: Path = _path_from_env("STUDIO_RAW_DIR", str(_runtime_root / "raw"))
    cookies_dir: Path = _path_from_env("STUDIO_COOKIES_DIR", str(_runtime_root / "cookies"))
    assets_dir: Path = _path_from_env("STUDIO_ASSETS_DIR", str(_runtime_root / "assets"))
    logs_dir: Path = _path_from_env("STUDIO_LOGS_DIR", str(_runtime_root / "logs"))
    libretranslate_url: str = os.getenv("LIBRETRANSLATE_URL", "")
    libretranslate_api_key: str = os.getenv("LIBRETRANSLATE_API_KEY", "")
    whisper_model: str = os.getenv("WHISPER_MODEL", "base")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")


settings = Settings()


def ensure_runtime_dirs() -> None:
    settings.runtime_root.mkdir(parents=True, exist_ok=True)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.download_dir.mkdir(parents=True, exist_ok=True)
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    settings.cookies_dir.mkdir(parents=True, exist_ok=True)
    settings.assets_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    (settings.output_dir / "transcribed").mkdir(parents=True, exist_ok=True)
    (settings.output_dir / "dubbed").mkdir(parents=True, exist_ok=True)
    (settings.output_dir / "temp").mkdir(parents=True, exist_ok=True)
