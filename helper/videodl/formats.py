"""Traduz modo/qualidade/formato escolhidos na extensão em parâmetros do yt-dlp."""

from __future__ import annotations

VIDEO_QUALITIES = ("best", "1080", "720", "480", "360")
AUDIO_QUALITIES = ("320", "192", "128")
VIDEO_EXTS = ("mp4", "mkv", "mov")
AUDIO_EXTS = ("mp3", "wav", "flac")
DEFAULT_EXT = {"video": "mp4", "audio": "mp3"}
LOSSLESS_AUDIO = ("wav", "flac")  # não têm kbps: a qualidade escolhida é ignorada


class InvalidOptions(ValueError):
    """Combinação de modo, qualidade e formato que não existe."""


def validate(mode: str, quality: str, ext: str | None = None) -> None:
    if mode == "video" and quality in VIDEO_QUALITIES and (ext is None or ext in VIDEO_EXTS):
        return
    if mode == "audio" and quality in AUDIO_QUALITIES and (ext is None or ext in AUDIO_EXTS):
        return
    raise InvalidOptions(f"combinação inválida: {mode}/{quality}/{ext}")


def final_extension(mode: str, ext: str | None = None) -> str:
    return ext or DEFAULT_EXT["audio" if mode == "audio" else "video"]


def build_format_opts(mode: str, quality: str, ext: str | None = None) -> dict:
    validate(mode, quality, ext)
    ext = final_extension(mode, ext)
    if mode == "audio":
        extract = {"key": "FFmpegExtractAudio", "preferredcodec": ext}
        if ext not in LOSSLESS_AUDIO:
            extract["preferredquality"] = quality
        return {"format": "ba/b", "noplaylist": True, "postprocessors": [extract]}

    if quality == "best":
        fmt = "bv*+ba/b"
        sort = ["res"]
    else:
        fmt = f"bv*[height<={quality}]+ba/b[height<={quality}]/bv*+ba/b"
        sort = [f"res:{quality}"]
    if ext != "mkv":  # MKV guarda os codecs originais; MP4/MOV preferem H.264/AAC para tocar em qualquer lugar
        sort += ["vcodec:h264", "acodec:aac"]
    return {
        "format": fmt,
        "format_sort": sort,
        "merge_output_format": ext,
        "noplaylist": True,
        # garante a extensão escolhida mesmo quando o melhor formato único vem em outro contêiner
        "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": ext}],
    }
