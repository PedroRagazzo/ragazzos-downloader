"""Pastas do programa e origem permitida da extensão."""

from __future__ import annotations

import os
import re
from pathlib import Path

EXTENSION_ID_FILE = Path(__file__).with_name("extension_id.txt")
_HINT = r"rode: helper\.venv\Scripts\python scripts\gen_extension_key.py"


def app_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "VideoDownloader"


def download_dir() -> Path:
    return Path.home() / "Downloads" / "Video Downloader"


def extension_origin(path: Path = EXTENSION_ID_FILE) -> str:
    try:
        ext_id = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise RuntimeError(f"ID da extensão não encontrado em {path}; {_HINT}") from None
    if not re.fullmatch(r"[a-p]{32}", ext_id):
        raise RuntimeError(f"ID da extensão inválido em {path}; {_HINT}")
    return f"chrome-extension://{ext_id}"
