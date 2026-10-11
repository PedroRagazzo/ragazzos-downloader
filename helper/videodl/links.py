"""Padroniza links para que variações de compartilhamento do mesmo vídeo sejam reconhecidas como iguais."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
_YOUTUBE_PATH_ID = re.compile(r"^/(?:shorts|embed|live|v)/([\w-]{6,})")
_VIDEO_ID = re.compile(r"^[\w-]{6,}$")

# parâmetros que só servem para rastrear quem compartilhou
_TRACKING = {
    "si", "feature", "igsh", "igshid", "is_from_webapp", "sender_device", "_r", "_t", "fbclid", "gclid",
    "share_app_id", "share_link_id", "social_sharing", "ref", "ref_src", "mibextid",
}


def _youtube_id(host: str, path: str, query: dict[str, str]) -> str | None:
    if host == "youtu.be":
        candidate = path.strip("/").split("/")[0]
    elif host in _YOUTUBE_HOSTS:
        match = _YOUTUBE_PATH_ID.match(path)
        candidate = match.group(1) if match else (query.get("v", "") if path == "/watch" else "")
    else:
        return None
    return candidate if _VIDEO_ID.match(candidate) else None


def normalize_url(url: str) -> str:
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        return url
    host = parts.netloc.lower()
    params = parse_qsl(parts.query, keep_blank_values=True)

    video_id = _youtube_id(host, parts.path, dict(params))
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"

    kept = [(k, v) for k, v in params if k.lower() not in _TRACKING and not k.lower().startswith("utm_")]
    return urlunsplit((parts.scheme.lower(), host, parts.path, urlencode(kept), ""))
