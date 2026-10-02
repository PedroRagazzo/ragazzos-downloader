"""Nomes de arquivo seguros para o Windows e sem conflito."""

from __future__ import annotations

import glob
import re
import unicodedata
from collections.abc import Collection
from pathlib import Path

MAX_TITLE = 150
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}


def sanitize_title(title: str | None) -> str:
    text = unicodedata.normalize("NFC", title or "")
    text = _INVALID.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip().rstrip(". ")
    text = text[:MAX_TITLE].rstrip(". ")
    if not text:
        return "video"
    if text.split(".")[0].upper() in _RESERVED:
        text = f"_{text}"
    return text


def site_tag(name: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower()) or "web"


def build_base_name(title: str | None, site: str | None) -> str:
    return f"{sanitize_title(title)} [{site_tag(site)}]"


def _in_use(folder: Path, base: str, taken: Collection[str]) -> bool:
    return base in taken or any(folder.glob(glob.escape(base) + ".*"))


def unique_base(folder: Path, base: str, taken: Collection[str] = frozenset()) -> str:
    candidate, n = base, 2
    while _in_use(folder, candidate, taken):
        candidate = f"{base} ({n})"
        n += 1
    return candidate
