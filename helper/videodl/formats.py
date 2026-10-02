"""Traduz modo/qualidade escolhidos na extensão em parâmetros do yt-dlp."""

from __future__ import annotations

VIDEO_QUALITIES = ("best", "1080", "720", "480", "360")
AUDIO_QUALITIES = ("320", "192", "128")


class InvalidOptions(ValueError):
    """Combinação de modo e qualidade que não existe."""


def validate(mode: str, quality: str) -> None:
    if mode == "video" and quality in VIDEO_QUALITIES:
        return
    if mode == "audio" and quality in AUDIO_QUALITIES:
        return
    raise InvalidOptions(f"combinação inválida: {mode}/{quality}")


def final_extension(mode: str) -> str:
    return "mp3" if mode == "audio" else "mp4"


def build_format_opts(mode: str, quality: str) -> dict:
    validate(mode, quality)
    if mode == "audio":
        return {
            "format": "ba/b",
            "noplaylist": True,
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": quality}
            ],
        }
    if quality == "best":
        fmt = "bv*+ba/b"
        sort = ["res", "vcodec:h264", "acodec:aac"]
    else:
        fmt = f"bv*[height<={quality}]+ba/b[height<={quality}]/bv*+ba/b"
        sort = [f"res:{quality}", "vcodec:h264", "acodec:aac"]
    return {
        "format": fmt,
        "format_sort": sort,
        "merge_output_format": "mp4",
        "noplaylist": True,
        # garante .mp4 mesmo quando o melhor formato único vem em outro contêiner
        "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}],
    }
