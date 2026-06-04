from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def require_binary(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise RuntimeError(f"Missing required binary: {name}. Install it and ensure it is on PATH.")
    return resolved


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Command failed"
        raise RuntimeError(message)
    return result


def safe_filename(value: str, fallback: str = "video") -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in value).strip()
    return cleaned[:120] or fallback


def resolve_existing_file(path: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise RuntimeError(f"File does not exist: {resolved}")
    return resolved
